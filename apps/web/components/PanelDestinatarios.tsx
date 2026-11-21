"use client";
/**
 * A quién le llega el incidente y plan de despacho multiagencia (reglas EMRE, SIMULADO).
 * Muestra cada agencia con su papel (líder, apoyo, informada) y la tarea EMRE que lo justifica.
 * El plan propone el recurso más cercano de cada agencia líder y de apoyo; un humano del PMU
 * lo confirma con un clic (la IA solo sugiere). Si ya hay despacho, completa el plan como refuerzo.
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import { newClientUuid } from "@/lib/dispatch";
import { formatInt, formatNumber } from "@/lib/format";
import {
  RECIPIENT_ROLE_LABEL,
  RECIPIENT_ROLE_STYLE,
  RESOURCE_TYPE_LABEL,
  type IncidentDetail,
} from "@/lib/labels";
import { EtiquetaSimulado } from "./EtiquetaSimulado";

interface Props {
  detail: IncidentDetail;
  onChanged: () => void | Promise<void>;
}

const CLOSED = ["descartado", "atendido", "duplicado"];

export function PanelDestinatarios({ detail, onChanged }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const routing = detail.routing;
  if (!routing) return null;

  const closed = CLOSED.includes(detail.status);
  const planned = routing.plan.filter((p) => p.candidate);
  const missing = routing.plan.filter((p) => !p.candidate && !p.already_dispatched);

  async function generate() {
    setBusy(true);
    setError(null);
    setDone(null);
    const { data, error: err } = await api.POST("/api/v1/incidents/{incident_id}/dispatch-plan", {
      params: { path: { incident_id: detail.id } },
      body: { client_uuid: newClientUuid(), resource_ids: routing!.plan_resource_ids },
    });
    setBusy(false);
    if (err || !data) {
      setError(
        (err as { detail?: string } | undefined)?.detail ?? "No se pudo generar el despacho",
      );
      return;
    }
    const agencies = Array.from(new Set(data.items.map((d) => d.agency.name)));
    setDone(`Despachados ${formatInt(data.items.length)} recursos: ${agencies.join(", ")}`);
    await onChanged();
  }

  return (
    <section className="rounded-lg bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">A quién le llega</h3>
        <EtiquetaSimulado />
      </div>

      {routing.held && (
        <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-900">
          {routing.hold_reason}. Confirme el incidente para avisar a las agencias.
        </p>
      )}

      {routing.recipients.length === 0 ? (
        <p className="mt-2 text-xs text-tinta-suave">
          Ninguna agencia de respuesta para esta categoría.
        </p>
      ) : (
        <ul className="mt-2 space-y-1">
          {routing.recipients.map((r) => (
            <li key={r.agency.id} className="flex items-start gap-2 text-xs">
              <span
                className={`mt-0.5 w-16 shrink-0 rounded px-1 text-center text-[10px] font-semibold ${
                  RECIPIENT_ROLE_STYLE[r.role]
                }`}
              >
                {RECIPIENT_ROLE_LABEL[r.role]}
              </span>
              <span className="flex-1">
                <strong>{r.agency.name}</strong>
                {r.dispatched && (
                  <span className="ml-1 rounded bg-violet-100 px-1 text-[10px] text-violet-800">
                    Despachada
                  </span>
                )}
                <span className="block text-tinta-suave">
                  {r.emre_task} · {r.reason}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {routing.notify_coe && (
        <p className="mt-2 text-xs">
          <span className="rounded bg-slate-800 px-1 text-[10px] font-semibold text-white">
            COE / UGR
          </span>{" "}
          <span className="text-tinta-suave">{routing.coe_reason}</span>
        </p>
      )}
      {routing.notes.map((n) => (
        <p key={n} className="mt-1 text-[11px] text-tinta-suave">
          {n}
        </p>
      ))}

      {!closed && routing.plan.length > 0 && (
        <div className="mt-3 border-t border-linea pt-2">
          <p className="text-xs font-semibold">Plan de despacho propuesto</p>
          <ul className="mt-1 space-y-0.5">
            {routing.plan.map((p, i) => (
              <li
                key={`${p.agency.id}-${p.candidate?.resource.id ?? i}`}
                className="flex justify-between gap-2 text-xs"
              >
                <span>
                  {p.agency.code} ·{" "}
                  {p.candidate
                    ? `${p.candidate.resource.label} (${RESOURCE_TYPE_LABEL[p.candidate.resource.type]})`
                    : p.already_dispatched
                      ? "ya despachada"
                      : "sin recursos disponibles"}
                </span>
                {p.candidate && (
                  <span className="shrink-0 tabular-nums text-tinta-suave">
                    {formatNumber(p.candidate.distance_m / 1000, 1)} km ·{" "}
                    {formatInt(Math.ceil(p.candidate.eta_min))} min
                  </span>
                )}
              </li>
            ))}
          </ul>
          {missing.length > 0 && (
            <p className="mt-1 text-[11px] text-amber-800">
              Sin recursos libres en: {missing.map((m) => m.agency.name).join(", ")}.
            </p>
          )}
          <button
            type="button"
            disabled={busy || planned.length === 0}
            onClick={generate}
            className="mt-2 w-full rounded bg-red-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {planned.length === 0
              ? "Plan completo"
              : `Generar despacho multiagencia (${formatInt(planned.length)})`}
          </button>
        </div>
      )}
      {done && <p className="mt-2 text-xs text-emerald-800">{done}</p>}
      {error && <p className="mt-2 text-xs text-rose-700">{error}</p>}
    </section>
  );
}
