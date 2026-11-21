"use client";
/**
 * Pantalla de la agencia de respuesta (specs/002 US1, FR-010): despachos de su agencia y
 * actualización de estado (llegada, atención finalizada, fuera de servicio con motivo).
 * En la demo, una sola credencial `agencia` puede actuar por cualquier agencia (spec, Supuestos).
 * Consulta cada 3 s; el cierre del incidente lo decide el PMU, no la agencia.
 */
import { DEMO_MODE } from "@/lib/env";
import { simulado } from "@/lib/env";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { isActive } from "@/lib/dispatch";
import { formatDateTime, formatNumber, formatTime } from "@/lib/format";
import {
  DISPATCH_STATUS_LABEL,
  EMRE_FUNCTION_LABEL,
  type AgencyOut,
  type DispatchOut,
} from "@/lib/labels";
import { clearSession, getSession } from "@/lib/session";

const AGENCY_KEY = "dacora.agency";
const REFRESH_MS = 3000;

function storedAgency(): string {
  try {
    return window.sessionStorage.getItem(AGENCY_KEY) ?? "";
  } catch {
    return "";
  }
}

type Action = "llegada" | "finalizar" | "fuera_de_servicio";

export default function PanelAgencia() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [agencies, setAgencies] = useState<AgencyOut[]>([]);
  const [agencyId, setAgencyId] = useState<string>(storedAgency);
  const [dispatches, setDispatches] = useState<DispatchOut[]>([]);
  const [cutoff, setCutoff] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [showClosed, setShowClosed] = useState(false);
  const allowed = session?.role === "pmu";

  useEffect(() => {
    if (!allowed) {
      router.replace("/ingresar/");
      return;
    }
    api.GET("/api/v1/agencies").then(({ data }) => setAgencies(data?.items ?? []));
  }, [allowed, router]);

  const fetchDispatches = useCallback(
    () =>
      api
        .GET("/api/v1/dispatches", { params: { query: { agency_id: agencyId } } })
        .then(({ data }) => {
          if (data) {
            setDispatches(data.items);
            setCutoff(data.cutoff_at);
          }
        }),
    [agencyId],
  );

  useEffect(() => {
    if (!allowed || !agencyId) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    const tick = () =>
      fetchDispatches().finally(() => {
        if (active) timer = setTimeout(tick, REFRESH_MS);
      });
    timer = setTimeout(tick, 0);
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [allowed, agencyId, fetchDispatches]);

  function choose(id: string) {
    setAgencyId(id);
    try {
      window.sessionStorage.setItem(AGENCY_KEY, id);
    } catch {
      /* sin almacenamiento: la elección vive solo en memoria */
    }
  }

  async function act(dispatch: DispatchOut, action: Action) {
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/dispatches/{dispatch_id}", {
      params: { path: { dispatch_id: dispatch.id } },
      body: { action, note: notes[dispatch.id]?.trim() || null },
    });
    if (err) {
      setError((err as { detail?: string }).detail ?? "No se pudo actualizar el despacho");
      return;
    }
    setNotes((n) => ({ ...n, [dispatch.id]: "" }));
    await fetchDispatches();
  }

  if (!allowed) return null;

  const agency = agencies.find((a) => a.id === agencyId);
  const visible = dispatches.filter((d) => showClosed || isActive(d.status));

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">Dacora · Agencia</h1>
        <EtiquetaSimulado />
        <button
          type="button"
          className="ml-auto text-sm text-tinta-suave"
          onClick={() => {
            clearSession();
            router.replace("/");
          }}
        >
          Salir
        </button>
      </header>

      <label className="flex flex-col gap-1 text-sm">
        Agencia
        <select
          className="rounded border border-linea bg-white px-2 py-1.5"
          value={agencyId}
          onChange={(e) => choose(e.target.value)}
        >
          <option value="">Elija su agencia…</option>
          {agencies.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} · {a.resources_available}/{a.resources_total} recursos disponibles
            </option>
          ))}
        </select>
      </label>

      {agency && (
        <p className="text-xs text-tinta-suave">
          {EMRE_FUNCTION_LABEL[agency.emre_function]} · se actualiza cada 3 s
          {DEMO_MODE && cutoff ? ` · corte ${formatDateTime(cutoff)}` : ""}
        </p>
      )}

      {agencyId && (
        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Despachos</h2>
            <label className="flex items-center gap-1 text-xs text-tinta-suave">
              <input
                type="checkbox"
                checked={showClosed}
                onChange={(e) => setShowClosed(e.target.checked)}
              />
              Mostrar finalizados y cancelados
            </label>
          </div>
          {visible.length === 0 && (
            <p className="rounded-lg bg-white p-4 text-sm text-tinta-suave shadow-sm">
              No hay despachos activos para esta agencia.
            </p>
          )}
          {visible.map((d) => (
            <article key={d.id} className="rounded-lg bg-white p-3 text-sm shadow-sm">
              <div className="flex justify-between gap-2">
                <span className="font-medium">
                  {d.resource.label}
                  {d.is_reinforcement && (
                    <span className="ml-1 rounded bg-amber-100 px-1 text-[10px]">Refuerzo</span>
                  )}
                </span>
                <span className="rounded bg-violet-100 px-1.5 text-xs font-semibold text-violet-800">
                  {DISPATCH_STATUS_LABEL[d.status]}
                </span>
              </div>
              <p className="text-xs text-tinta-suave">
                Despachado {formatTime(d.created_at)} · {formatNumber(d.distance_m / 1000, 1)} km ·
                llegada estimada {formatTime(d.eta_at)}
                {simulado(" (SIMULADA)")}
                {d.arrived_at && ` · llegó ${formatTime(d.arrived_at)}`}
              </p>
              <p className="text-xs text-tinta-suave">Incidente {d.incident_id.slice(0, 8)}</p>
              {isActive(d.status) && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {d.status === "en_camino" && (
                    <button
                      type="button"
                      onClick={() => act(d, "llegada")}
                      className="rounded bg-teal-700 px-3 py-1 text-xs font-medium text-white"
                    >
                      Llegamos al sitio
                    </button>
                  )}
                  {d.status === "en_sitio" && (
                    <button
                      type="button"
                      onClick={() => act(d, "finalizar")}
                      className="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white"
                    >
                      Atención finalizada
                    </button>
                  )}
                  <input
                    className="min-w-40 flex-1 rounded border border-linea px-2 py-1 text-xs"
                    placeholder="Motivo (para fuera de servicio)"
                    value={notes[d.id] ?? ""}
                    onChange={(e) => setNotes((n) => ({ ...n, [d.id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    disabled={!notes[d.id]?.trim()}
                    onClick={() => act(d, "fuera_de_servicio")}
                    className="rounded border border-slate-400 px-3 py-1 text-xs disabled:opacity-40"
                  >
                    Fuera de servicio
                  </button>
                </div>
              )}
              {d.close_note && (
                <p className="mt-1 text-xs text-tinta-suave">Motivo: {d.close_note}</p>
              )}
            </article>
          ))}
        </section>
      )}
      {error && <p className="text-sm text-rose-700">{error}</p>}
    </main>
  );
}
