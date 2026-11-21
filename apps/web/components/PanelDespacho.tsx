"use client";
/**
 * Despacho de un incidente (specs/002 US1): función EMRE y agencia sugeridas, recursos
 * disponibles por cercanía con ETA SIMULADA, refuerzo justificado si ya hay un despacho activo,
 * cancelación con motivo y cierre "atendido" (decisión humana, FR-011).
 */
import { EtiquetaSimulado } from "./EtiquetaSimulado";
import { simulado } from "@/lib/env";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { isActive, newClientUuid, readyToClose } from "@/lib/dispatch";
import { formatInt, formatNumber, formatTime } from "@/lib/format";
import {
  DISPATCH_STATUS_LABEL,
  RESOURCE_TYPE_LABEL,
  type DispatchOut,
  type IncidentDetail,
} from "@/lib/labels";

interface Props {
  detail: IncidentDetail;
  onChanged: () => void | Promise<void>;
}

interface ApiError {
  detail?: string;
  code?: string;
  active?: DispatchOut[];
}

const CLOSED = ["descartado", "atendido"];

export function PanelDespacho({ detail, onChanged }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<DispatchOut[] | null>(null);
  const [justification, setJustification] = useState("");
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [cancelNote, setCancelNote] = useState("");

  const suggestion = detail.suggestion;
  const dispatches = detail.dispatches ?? [];
  const active = dispatches.filter((d) => isActive(d.status));
  const closed = CLOSED.includes(detail.status);
  const reinforcing = conflict !== null || active.length > 0;

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  async function dispatch() {
    setBusy(true);
    setError(null);
    const { error: err } = await api.POST("/api/v1/dispatches", {
      body: {
        client_uuid: newClientUuid(),
        incident_id: detail.id,
        resource_ids: selected,
        is_reinforcement: reinforcing,
        justification: reinforcing ? justification.trim() || null : null,
      },
    });
    setBusy(false);
    if (err) {
      const e = err as ApiError;
      if (e.code === "active_dispatch_exists") setConflict(e.active ?? []);
      setError(e.detail ?? "No se pudo despachar");
      return;
    }
    setSelected([]);
    setConflict(null);
    setJustification("");
    await onChanged();
  }

  async function cancel(id: string) {
    setBusy(true);
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/dispatches/{dispatch_id}", {
      params: { path: { dispatch_id: id } },
      body: { action: "cancelar", note: cancelNote.trim() || null },
    });
    setBusy(false);
    if (err) {
      setError((err as ApiError).detail ?? "No se pudo cancelar");
      return;
    }
    setCancelling(null);
    setCancelNote("");
    await onChanged();
  }

  async function closeAttended() {
    setBusy(true);
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/incidents/{incident_id}", {
      params: { path: { incident_id: detail.id } },
      body: { action: "cerrar_atendido" },
    });
    setBusy(false);
    if (err) setError((err as ApiError).detail ?? "No se pudo cerrar");
    else await onChanged();
  }

  const finishedButUnverified =
    detail.status !== "verificado" &&
    !closed &&
    dispatches.some((d) => d.status === "finalizado") &&
    active.length === 0;

  return (
    <section className="rounded-lg bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Despacho</h3>
        <EtiquetaSimulado />
      </div>

      {dispatches.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {dispatches.map((d) => (
            <li key={d.id} className="rounded border border-linea p-2 text-xs">
              <div className="flex justify-between gap-2">
                <span className="font-medium">
                  {d.agency.name} · {d.resource.label}
                  {d.is_reinforcement && (
                    <span className="ml-1 rounded bg-amber-100 px-1 text-[10px]">Refuerzo</span>
                  )}
                </span>
                <span
                  className={`shrink-0 rounded px-1.5 text-[10px] font-semibold ${
                    isActive(d.status) ? "bg-violet-100 text-violet-800" : "bg-slate-100"
                  }`}
                >
                  {DISPATCH_STATUS_LABEL[d.status]}
                </span>
              </div>
              <p className="text-tinta-suave">
                Salió {formatTime(d.created_at)} · {formatNumber(d.distance_m / 1000, 1)} km ·
                llegada estimada {formatTime(d.eta_at)}
                {simulado(" (SIMULADA)")}
                {d.arrived_at && ` · llegó ${formatTime(d.arrived_at)}`}
              </p>
              {d.justification && <p className="text-tinta-suave">“{d.justification}”</p>}
              {d.close_note && <p className="text-tinta-suave">Motivo: {d.close_note}</p>}
              {isActive(d.status) &&
                (cancelling === d.id ? (
                  <div className="mt-1 flex gap-1">
                    <input
                      className="flex-1 rounded border border-linea px-1 py-0.5"
                      placeholder="Motivo de la cancelación"
                      value={cancelNote}
                      onChange={(e) => setCancelNote(e.target.value)}
                    />
                    <button
                      type="button"
                      disabled={busy || !cancelNote.trim()}
                      onClick={() => cancel(d.id)}
                      className="rounded bg-rose-700 px-2 text-white disabled:opacity-40"
                    >
                      Cancelar despacho
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setCancelling(d.id)}
                    className="mt-1 text-[11px] text-rose-700 underline"
                  >
                    Cancelar…
                  </button>
                ))}
            </li>
          ))}
        </ul>
      )}

      {readyToClose(detail) && (
        <div className="mt-2 rounded bg-emerald-50 p-2 text-xs">
          <p className="font-medium text-emerald-900">Listo para cerrar: la agencia finalizó.</p>
          <button
            type="button"
            disabled={busy}
            onClick={closeAttended}
            className="mt-1 rounded bg-emerald-700 px-3 py-1 text-white disabled:opacity-40"
          >
            Cerrar como atendido
          </button>
        </div>
      )}
      {finishedButUnverified && (
        <p className="mt-2 text-[11px] text-tinta-suave">
          La agencia finalizó. Confirme el incidente para poder cerrarlo como atendido.
        </p>
      )}

      {!closed && suggestion && (
        <div className="mt-3">
          <p className="text-xs text-tinta-suave">
            {suggestion.emre_function_label ?? "Sin agencia sugerida para esta categoría"}
            {suggestion.suggested_agency && (
              <>
                {" "}
                → <strong>{suggestion.suggested_agency.name}</strong>
              </>
            )}
            {suggestion.alternative_agencies.length > 0 && (
              <span className="text-tinta-suave">
                {" "}
                (alternativas: {suggestion.alternative_agencies.map((a) => a.name).join(", ")})
              </span>
            )}
          </p>
          {suggestion.fallback_used && (
            <p className="mt-1 text-[11px] text-amber-800">
              La agencia sugerida no tiene recursos disponibles: se listan los de las agencias
              alternativas de la misma función.
            </p>
          )}
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
            {suggestion.candidates.map((c) => (
              <li key={c.resource.id}>
                <label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-papel">
                  <input
                    type="checkbox"
                    checked={selected.includes(c.resource.id)}
                    onChange={() => toggle(c.resource.id)}
                  />
                  <span className="flex-1">
                    {c.resource.label}{" "}
                    <span className="text-tinta-suave">
                      · {RESOURCE_TYPE_LABEL[c.resource.type]} · {c.agency_code}
                    </span>
                  </span>
                  <span className="tabular-nums text-tinta-suave">
                    {formatNumber(c.distance_m / 1000, 1)} km · {formatInt(Math.ceil(c.eta_min))}{" "}
                    min
                  </span>
                </label>
              </li>
            ))}
            {suggestion.candidates.length === 0 && (
              <li className="text-xs text-tinta-suave">No hay recursos disponibles.</li>
            )}
          </ul>

          {reinforcing && (
            <div className="mt-2 rounded bg-amber-50 p-2 text-xs">
              <p className="font-medium text-amber-900">
                Ya hay un despacho activo. Para enviar más recursos, márquelo como refuerzo y
                justifíquelo (queda en la bitácora).
              </p>
              {conflict?.map((d) => (
                <p key={d.id} className="text-amber-900">
                  Activo: {d.agency.name} · {d.resource.label} · {DISPATCH_STATUS_LABEL[d.status]}{" "}
                  desde {formatTime(d.created_at)}
                </p>
              ))}
              <textarea
                className="mt-1 w-full rounded border border-amber-300 p-1"
                rows={2}
                placeholder="Justificación del refuerzo"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
              />
            </div>
          )}

          <button
            type="button"
            disabled={busy || selected.length === 0 || (reinforcing && !justification.trim())}
            onClick={dispatch}
            className="mt-2 w-full rounded bg-violet-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {reinforcing ? "Despachar refuerzo" : "Despachar"} ({formatInt(selected.length)})
          </button>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-rose-700">{error}</p>}
    </section>
  );
}
