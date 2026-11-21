"use client";
/**
 * Datos que siguen visibles sin conexión (offline-first, principio II): cada respuesta buena se
 * guarda en IndexedDB (tabla `kv`); si la petición falla, se muestra la última guardada con su
 * fecha. Al volver la conexión (`online`) se pide de nuevo y se recalcula.
 */
import { useEffect, useRef, useState } from "react";
import { db } from "@/lib/db";

interface Snapshot<T> {
  data: T;
  savedAt: string;
}

const PREFIX = "snapshot:";

async function save<T>(key: string, data: T): Promise<string> {
  const savedAt = new Date().toISOString();
  try {
    await db.kv.put({ key: PREFIX + key, value: { data, savedAt } satisfies Snapshot<T> });
  } catch {
    /* sin IndexedDB (modo privado): se sigue mostrando lo que está en memoria */
  }
  return savedAt;
}

async function load<T>(key: string): Promise<Snapshot<T> | null> {
  try {
    const item = await db.kv.get(PREFIX + key);
    return (item?.value as Snapshot<T> | undefined) ?? null;
  } catch {
    return null;
  }
}

export interface OfflineData<T> {
  data: T | null;
  /** Hora de los datos mostrados (la de la última respuesta recibida). */
  savedAt: string | null;
  /** `true` si lo mostrado viene de la última copia guardada porque no hay conexión. */
  offline: boolean;
}

interface Options {
  enabled?: boolean;
  /** Cambiarlo fuerza una nueva consulta (p. ej. un evento en vivo). */
  refreshKey?: number;
  /** Consulta periódica en milisegundos (sin flujo en vivo, como en el inicio público). */
  pollMs?: number;
}

export function useOfflineData<T>(
  key: string,
  fetcher: () => Promise<T | undefined>,
  { enabled = true, refreshKey = 0, pollMs }: Options = {},
): OfflineData<T> {
  const [state, setState] = useState<OfflineData<T>>({ data: null, savedAt: null, offline: false });
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    if (!enabled) return;
    let active = true;

    const fallback = () =>
      load<T>(key).then((snap) => {
        if (!active) return;
        setState((prev) =>
          prev.data !== null
            ? { ...prev, offline: true }
            : { data: snap?.data ?? null, savedAt: snap?.savedAt ?? null, offline: true },
        );
      });

    const run = () => {
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        void fallback();
        return;
      }
      fetcherRef
        .current()
        .then(async (data) => {
          if (!active) return;
          if (data === undefined) {
            await fallback();
            return;
          }
          const savedAt = await save(key, data);
          if (active) setState({ data, savedAt, offline: false });
        })
        .catch(() => void fallback());
    };

    const goOffline = () => setState((prev) => ({ ...prev, offline: true }));
    window.addEventListener("online", run);
    window.addEventListener("offline", goOffline);
    const first = setTimeout(run, 0);
    const timer = pollMs ? setInterval(run, pollMs) : null;
    return () => {
      active = false;
      clearTimeout(first);
      if (timer) clearInterval(timer);
      window.removeEventListener("online", run);
      window.removeEventListener("offline", goOffline);
    };
  }, [key, enabled, refreshKey, pollMs]);

  return state;
}
