"use client";
/**
 * Datos en vivo del tablero (contracts/sse-events.md): SSE con respaldo por polling REST.
 * Tras 2 fallos seguidos del stream, consulta GET /incidents?since= cada 3 s y avisa
 * "Modo de respaldo"; reintenta el stream cada 30 s.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api/client";
import type { IncidentSummary } from "@/lib/labels";

export type LiveMode = "conectando" | "en_vivo" | "respaldo";

interface LiveState {
  incidents: Map<string, IncidentSummary>;
  mode: LiveMode;
  cutoffAt: string | null;
  /** Se incrementa con cada cambio; útil para refrescar capas derivadas. */
  revision: number;
  kpiRevision: number;
}

const POLL_MS = 3000;
const RETRY_SSE_MS = 30000;

export function useLiveIncidents(token: string | null) {
  const [state, setState] = useState<LiveState>({
    incidents: new Map(),
    mode: "conectando",
    cutoffAt: null,
    revision: 0,
    kpiRevision: 0,
  });
  const lastUpdated = useRef<string | null>(null);

  const upsert = useCallback((items: IncidentSummary[], cutoffAt?: string) => {
    setState((prev) => {
      const next = new Map(prev.incidents);
      for (const item of items) {
        if (item.report_count > 0) next.set(item.id, item);
        else next.delete(item.id);
        if (!lastUpdated.current || item.updated_at > lastUpdated.current) {
          lastUpdated.current = item.updated_at;
        }
      }
      return {
        ...prev,
        incidents: next,
        cutoffAt: cutoffAt ?? new Date().toISOString(),
        revision: prev.revision + 1,
      };
    });
  }, []);

  const replaceAll = useCallback(
    (items: IncidentSummary[], cutoffAt: string) => {
      lastUpdated.current = null;
      setState((prev) => ({ ...prev, incidents: new Map(), revision: prev.revision + 1 }));
      upsert(items, cutoffAt);
    },
    [upsert],
  );

  const reload = useCallback(async () => {
    const { data } = await api.GET("/api/v1/incidents", { params: { query: { limit: 2000 } } });
    if (data) replaceAll(data.items, data.cutoff_at);
  }, [replaceAll]);

  useEffect(() => {
    if (!token) return;
    let source: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let failures = 0;
    let closed = false;

    const poll = async () => {
      const since = lastUpdated.current ?? undefined;
      const { data } = await api.GET("/api/v1/incidents", {
        params: { query: { limit: 2000, since } },
      });
      if (data) upsert(data.items, data.cutoff_at);
    };

    const startPolling = () => {
      if (pollTimer) return;
      setState((p) => ({ ...p, mode: "respaldo" }));
      pollTimer = setInterval(() => void poll(), POLL_MS);
      retryTimer = setTimeout(connect, RETRY_SSE_MS);
    };

    function connect() {
      if (closed) return;
      source?.close();
      source = new EventSource(
        `${API_BASE}/api/v1/stream?token=${encodeURIComponent(token ?? "")}`,
      );
      source.onopen = () => {
        failures = 0;
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null;
        setState((p) => ({ ...p, mode: "en_vivo" }));
        void poll(); // ponerse al día con lo ocurrido durante la desconexión
      };
      source.onerror = () => {
        failures += 1;
        if (failures >= 2) {
          source?.close();
          startPolling();
        }
      };
      source.addEventListener("incident.upserted", (e) => {
        upsert([JSON.parse((e as MessageEvent).data) as IncidentSummary]);
      });
      source.addEventListener("kpi.updated", () => {
        setState((p) => ({ ...p, kpiRevision: p.kpiRevision + 1 }));
      });
      source.addEventListener("demo.reset", () => void reload());
    }

    api
      .GET("/api/v1/incidents", { params: { query: { limit: 2000 } } })
      .then(({ data }) => {
        if (data) replaceAll(data.items, data.cutoff_at);
      })
      .finally(connect);
    return () => {
      closed = true;
      source?.close();
      if (pollTimer) clearInterval(pollTimer);
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [token, upsert, reload, replaceAll]);

  return { ...state, reload };
}
