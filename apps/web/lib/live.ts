"use client";
/**
 * Datos en vivo del tablero (contracts/sse-events.md de 001 y 002): SSE con respaldo por polling.
 * Tras 2 fallos seguidos del stream, consulta GET /incidents?since= (y despachos, recursos y
 * borradores de alertas) cada 3 s y avisa "Modo de respaldo"; reintenta el stream cada 30 s.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api/client";
import { isActive, toPoint, type ResourcePoint } from "@/lib/dispatch";
import type { DispatchOut, IncidentSummary } from "@/lib/labels";

export type LiveMode = "conectando" | "en_vivo" | "respaldo";

interface LiveState {
  incidents: Map<string, IncidentSummary>;
  dispatches: Map<string, DispatchOut>;
  resources: Map<string, ResourcePoint>;
  /** Recorrido [lon, lat] por despacho activo. */
  trails: Map<string, [number, number][]>;
  mode: LiveMode;
  cutoffAt: string | null;
  /** Se incrementa con cada cambio; útil para refrescar capas derivadas. */
  revision: number;
  kpiRevision: number;
  /** Cambios de alertas (crear, aprobar, anular…). */
  alertRevision: number;
  /** La capa de cascada debe recalcularse (lluvia o reportes relevantes). */
  cascadeRevision: number;
}

interface ResourceMoved {
  resource_id: string;
  code: string;
  status: ResourcePoint["status"];
  lat: number;
  lon: number;
  dispatch_id: string | null;
}

const POLL_MS = 3000;
const RETRY_SSE_MS = 30000;

async function loadDispatchLayer() {
  const [resources, dispatches] = await Promise.all([
    api.GET("/api/v1/resources"),
    api.GET("/api/v1/dispatches"),
  ]);
  const active = (dispatches.data?.items ?? []).filter((d) => isActive(d.status));
  const trails = new Map<string, [number, number][]>();
  await Promise.all(
    active.map(async (d) => {
      const { data } = await api.GET("/api/v1/resources/{resource_id}/tracks", {
        params: { path: { resource_id: d.resource.id } },
      });
      trails.set(
        d.id,
        (data?.items ?? [])
          .filter((t) => t.dispatch_id === d.id)
          .map((t) => [t.lon, t.lat] as [number, number]),
      );
    }),
  );
  return {
    resources: new Map((resources.data?.items ?? []).map((r) => [r.id, toPoint(r)])),
    dispatches: new Map((dispatches.data?.items ?? []).map((d) => [d.id, d])),
    trails,
  };
}

export function useLiveIncidents(token: string | null) {
  const [state, setState] = useState<LiveState>({
    incidents: new Map(),
    dispatches: new Map(),
    resources: new Map(),
    trails: new Map(),
    mode: "conectando",
    cutoffAt: null,
    revision: 0,
    kpiRevision: 0,
    alertRevision: 0,
    cascadeRevision: 0,
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

  const upsertDispatch = useCallback((d: DispatchOut) => {
    setState((prev) => {
      const dispatches = new Map(prev.dispatches).set(d.id, d);
      const resources = new Map(prev.resources).set(d.resource.id, toPoint(d.resource));
      const trails = new Map(prev.trails);
      if (!isActive(d.status)) trails.delete(d.id);
      else if (!trails.has(d.id)) trails.set(d.id, [[d.resource.lon, d.resource.lat]]);
      return { ...prev, dispatches, resources, trails, revision: prev.revision + 1 };
    });
  }, []);

  const moveResource = useCallback((m: ResourceMoved) => {
    setState((prev) => {
      const resources = new Map(prev.resources);
      const current = resources.get(m.resource_id);
      resources.set(m.resource_id, {
        id: m.resource_id,
        code: m.code,
        label: current?.label ?? m.code,
        status: m.status,
        lat: m.lat,
        lon: m.lon,
      });
      const trails = new Map(prev.trails);
      if (m.dispatch_id && trails.has(m.dispatch_id)) {
        trails.set(m.dispatch_id, [...(trails.get(m.dispatch_id) ?? []), [m.lon, m.lat]]);
      }
      return { ...prev, resources, trails };
    });
  }, []);

  const refreshDispatchLayer = useCallback(async () => {
    const layer = await loadDispatchLayer();
    setState((prev) => ({ ...prev, ...layer }));
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
    await refreshDispatchLayer();
    setState((p) => ({
      ...p,
      alertRevision: p.alertRevision + 1,
      cascadeRevision: p.cascadeRevision + 1,
    }));
  }, [replaceAll, refreshDispatchLayer]);

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

    const pollAll = async () => {
      await poll();
      await refreshDispatchLayer();
      setState((p) => ({ ...p, alertRevision: p.alertRevision + 1 }));
    };

    const startPolling = () => {
      if (pollTimer) return;
      setState((p) => ({ ...p, mode: "respaldo" }));
      pollTimer = setInterval(() => void pollAll(), POLL_MS);
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
      source.addEventListener("dispatch.upserted", (e) => {
        upsertDispatch(JSON.parse((e as MessageEvent).data) as DispatchOut);
      });
      source.addEventListener("resource.moved", (e) => {
        moveResource(JSON.parse((e as MessageEvent).data) as ResourceMoved);
      });
      source.addEventListener("alert.changed", () => {
        setState((p) => ({ ...p, alertRevision: p.alertRevision + 1 }));
      });
      source.addEventListener("cascade.invalidated", () => {
        setState((p) => ({ ...p, cascadeRevision: p.cascadeRevision + 1 }));
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
      .then(refreshDispatchLayer)
      .finally(connect);
    return () => {
      closed = true;
      source?.close();
      if (pollTimer) clearInterval(pollTimer);
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [token, upsert, upsertDispatch, moveResource, refreshDispatchLayer, reload, replaceAll]);

  return { ...state, reload, refreshDispatchLayer };
}
