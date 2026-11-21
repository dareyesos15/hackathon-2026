"use client";
/**
 * Detalle de un incidente (FR-024, FR-025): reportes redactados, desglose explicable del puntaje
 * de veracidad y decisión humana (Confirmar / Descartar / Marcar duplicado / Reabrir).
 * La IA solo sugiere; descartar algo con riesgo vital exige una nota (principio III).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt, formatTime } from "@/lib/format";
import {
  CATEGORY_LABEL,
  CHANNEL_LABEL,
  SIGNAL_LABEL,
  STATUS_LABEL,
  TRIAGE_COLOR,
  TRIAGE_LABEL,
  TRUST_LABEL,
  TRUST_STYLE,
  type IncidentDetail,
  type IncidentSummary,
} from "@/lib/labels";
import { EtiquetaSimulado } from "./EtiquetaSimulado";
import { IconoCategoria } from "./IconoCategoria";
import { PanelDespacho } from "./PanelDespacho";

type Action = "confirmar" | "descartar" | "marcar_duplicado" | "reabrir";

interface Signal {
  puntos: number;
  max: number;
  min?: number;
  detalle: string;
}

interface Props {
  incidentId: string;
  incidents: IncidentSummary[];
  revision: number;
  onClose: () => void;
  onSelect: (id: string) => void;
  /** Abre el editor de alertas precargado con el área y el tipo del incidente (US2). */
  onCreateAlert?: (incident: IncidentDetail) => void;
}

const ACTION_LABEL: Record<Action, string> = {
  confirmar: "Confirmar",
  descartar: "Descartar",
  marcar_duplicado: "Marcar duplicado",
  reabrir: "Reabrir",
};

const EVENT_LABEL: Record<string, string> = {
  ingerido: "Recibido y procesado",
  agrupado: "Agrupado por el sistema",
  confirmar: "Confirmado",
  descartar: "Descartado",
  marcar_duplicado: "Marcado como duplicado",
  reabrir: "Reabierto",
  despachar: "Despachado",
  reforzar: "Refuerzo despachado",
  despacho_estado: "Cambio de estado del despacho",
  cancelar_despacho: "Despacho cancelado",
  despacho_doble_bloqueado: "Doble despacho bloqueado",
  cerrar_atendido: "Cerrado como atendido",
};

function distanceKm(a: IncidentSummary, b: IncidentSummary): number {
  if (a.lat === null || a.lon === null || b.lat === null || b.lon === null) return Infinity;
  const dLat = (b.lat - a.lat) * 111;
  const dLon = (b.lon - a.lon) * 111 * Math.cos((a.lat * Math.PI) / 180);
  return Math.hypot(dLat, dLon);
}

export function DetalleIncidente({
  incidentId,
  incidents,
  revision,
  onClose,
  onSelect,
  onCreateAlert,
}: Props) {
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [note, setNote] = useState("");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const { data, error: err } = await api.GET("/api/v1/incidents/{incident_id}", {
      params: { path: { incident_id: incidentId } },
    });
    if (data) setDetail(data);
    else if (err) setError("No se pudo cargar el incidente");
  }, [incidentId]);

  useEffect(() => {
    let active = true;
    api
      .GET("/api/v1/incidents/{incident_id}", { params: { path: { incident_id: incidentId } } })
      .then(({ data }) => {
        if (active && data) setDetail(data);
      });
    return () => {
      active = false;
    };
  }, [incidentId, revision]);

  const nearby = useMemo(() => {
    if (!detail) return [];
    return incidents
      .filter((i) => i.id !== detail.id)
      .map((i) => ({ i, d: distanceKm(detail, i) }))
      .filter(({ d }) => d < 2)
      .sort((a, b) => a.d - b.d)
      .slice(0, 8);
  }, [detail, incidents]);

  if (!detail) {
    return <div className="p-4 text-sm text-tinta-suave">{error ?? "Cargando incidente…"}</div>;
  }

  const breakdown = detail.trust_breakdown as Record<string, Signal | number | string>;
  const signals = Object.entries(breakdown).filter(
    (entry): entry is [string, Signal] => typeof entry[1] === "object" && entry[1] !== null,
  );
  const pending = detail.reports.some((r) => r.status === "en_revision");
  const closed = detail.reports.some((r) =>
    ["verificado", "descartado", "duplicado"].includes(r.status),
  );
  const needsNote = detail.is_life_threat && note.trim() === "";

  async function act(action: Action) {
    setBusy(true);
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/incidents/{incident_id}", {
      params: { path: { incident_id: incidentId } },
      body: {
        action,
        note: note.trim() || null,
        duplicate_of_incident: action === "marcar_duplicado" ? target || null : null,
      },
    });
    setBusy(false);
    if (err) {
      setError((err as { detail?: string }).detail ?? "No se pudo registrar la decisión");
      return;
    }
    setNote("");
    if (action === "marcar_duplicado" && target) onSelect(target);
    else await load();
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <IconoCategoria category={detail.category} triage={detail.triage_level} size={36} />
            <h2 className="font-display text-2xl font-semibold leading-tight">
              {CATEGORY_LABEL[detail.category]}
            </h2>
            <EtiquetaSimulado />
          </div>
          <p className="text-xs text-tinta-suave">
            <span className="font-bold" style={{ color: TRIAGE_COLOR[detail.triage_level] }}>
              {TRIAGE_LABEL[detail.triage_level]}
            </span>
            {detail.is_life_threat && (
              <span className="ml-1 rounded-sm bg-senal px-1 font-bold text-white">
                Riesgo vital
              </span>
            )}{" "}
            · {STATUS_LABEL[detail.status]} · desde {formatDateTime(detail.first_seen)}
          </p>
          <Ubicacion detail={detail} />
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded px-2 text-sm text-tinta-suave hover:bg-papel"
          aria-label="Cerrar detalle"
        >
          ✕
        </button>
      </div>

      <section className="rounded-lg bg-white p-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Puntaje de veracidad</h3>
          <span
            className={`rounded border px-2 py-0.5 text-sm font-bold ${TRUST_STYLE[detail.trust_label]}`}
          >
            {detail.trust_score} · {TRUST_LABEL[detail.trust_label]}
          </span>
        </div>
        <ul className="mt-2 space-y-1.5">
          {signals.map(([key, s]) => {
            const negative = s.puntos < 0;
            const width = negative
              ? (Math.abs(s.puntos) / Math.abs(s.min ?? 15)) * 100
              : s.max
                ? (s.puntos / s.max) * 100
                : 0;
            return (
              <li key={key} className="text-xs">
                <div className="flex justify-between">
                  <span className="font-medium">{SIGNAL_LABEL[key] ?? key}</span>
                  <span className={`tabular-nums ${negative ? "text-senal" : ""}`}>
                    {s.puntos > 0 ? "+" : ""}
                    {s.puntos.toLocaleString("es-CO", { maximumFractionDigits: 1 })}
                    {negative ? ` (mín. ${s.min})` : ` / ${s.max}`}
                  </span>
                </div>
                <div className="h-1.5 rounded bg-papel">
                  <div
                    className={`h-1.5 rounded ${negative ? "bg-senal" : "bg-tinta"}`}
                    style={{ width: `${Math.min(100, Math.max(0, width))}%` }}
                  />
                </div>
                <p className="text-[11px] text-tinta-suave">{s.detalle}</p>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-[10px] text-tinta-suave">
          Modelo {String(breakdown.version_modelo ?? "")} · la IA sugiere, decide un humano.
        </p>
      </section>

      <section className="rounded-lg bg-white p-3">
        <h3 className="text-sm font-semibold">Decisión del PMU</h3>
        <textarea
          className="mt-2 w-full rounded border border-linea p-2 text-sm"
          rows={2}
          placeholder={
            detail.is_life_threat
              ? "Nota obligatoria para descartar un reporte con riesgo vital"
              : "Nota (opcional)"
          }
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !pending}
            onClick={() => act("confirmar")}
            className="rounded bg-verificado px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {ACTION_LABEL.confirmar}
          </button>
          <button
            type="button"
            disabled={busy || !pending || needsNote}
            onClick={() => act("descartar")}
            title={needsNote ? "Escriba una nota: el incidente tiene riesgo vital" : undefined}
            className="rounded bg-senal px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {ACTION_LABEL.descartar}
          </button>
          {closed && (
            <button
              type="button"
              disabled={busy}
              onClick={() => act("reabrir")}
              className="rounded border border-tinta-suave px-3 py-1.5 text-sm disabled:opacity-40"
            >
              {ACTION_LABEL.reabrir}
            </button>
          )}
        </div>
        {needsNote && pending && (
          <p className="mt-1 text-[11px] text-senal">
            Riesgo vital: para descartar debe dejar una nota que quede en la bitácora.
          </p>
        )}
        {pending && nearby.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <select
              aria-label="Incidente original"
              className="flex-1 rounded border border-linea bg-white px-2 py-1 text-xs"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Duplicado de… (incidentes cercanos)</option>
              {nearby.map(({ i, d }) => (
                <option key={i.id} value={i.id}>
                  {CATEGORY_LABEL[i.category]} · {i.barrio ?? "—"} ·{" "}
                  {d.toLocaleString("es-CO", { maximumFractionDigits: 1 })} km ·{" "}
                  {formatInt(i.report_count)} rep.
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={busy || !target}
              onClick={() => act("marcar_duplicado")}
              className="rounded bg-tinta px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
            >
              {ACTION_LABEL.marcar_duplicado}
            </button>
          </div>
        )}
        {error && <p className="mt-2 text-xs text-senal">{error}</p>}
      </section>

      <PanelDespacho detail={detail} onChanged={load} />

      {onCreateAlert && (
        <button
          type="button"
          onClick={() => onCreateAlert(detail)}
          className="rounded border border-amber-500 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-900"
        >
          Crear alerta desde este incidente
        </button>
      )}

      <section className="rounded-lg bg-white p-3">
        <h3 className="text-sm font-semibold">
          Reportes ({formatInt(detail.reports.length)}) · {formatInt(detail.independent_sources)}{" "}
          fuentes independientes
        </h3>
        <ul className="mt-2 space-y-2">
          {detail.reports.map((r) => (
            <li key={r.id} className="rounded border border-linea p-2 text-xs">
              <div className="flex justify-between text-tinta-suave">
                <span>
                  {CHANNEL_LABEL[r.channel]} · {formatTime(r.occurred_at)} · precisión{" "}
                  {r.geo_precision}
                </span>
                <span>{r.status.replace("_", " ")}</span>
              </div>
              <p className="mt-1 text-tinta">{r.text_redacted}</p>
              {r.misinfo_signals.length > 0 && (
                <p className="mt-1 text-senal">
                  Señales de desinformación: {r.misinfo_signals.join(", ")}
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg bg-white p-3">
        <h3 className="text-sm font-semibold">Bitácora</h3>
        <ol className="mt-2 space-y-1 text-xs">
          {detail.events.map((e) => (
            <li key={e.id} className="flex justify-between gap-2">
              <span>
                {EVENT_LABEL[e.action] ?? e.action}
                {typeof e.payload.nota === "string" && (
                  <span className="text-tinta-suave"> — “{e.payload.nota}”</span>
                )}
                {typeof e.payload.recurso === "string" && (
                  <span className="text-slate-500">
                    {" "}
                    — {String(e.payload.agencia)} · {e.payload.recurso}
                  </span>
                )}
                {typeof e.payload.estado === "string" && (
                  <span className="text-slate-500"> — {e.payload.estado.replace("_", " ")}</span>
                )}
              </span>
              <span className="shrink-0 text-tinta-suave">
                {e.actor_role === "sistema" ? "sistema" : e.actor_role} · {formatTime(e.at)}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

/** Dónde está el incidente y cómo se ubicó: con GPS el barrio sale del punto en el mapa. */
function Ubicacion({ detail }: { detail: IncidentDetail }) {
  const hasPoint = detail.lat !== null && detail.lon !== null;
  const coords = hasPoint ? `${detail.lat?.toFixed(5)}, ${detail.lon?.toFixed(5)}` : null;
  let how: string;
  switch (detail.geo_precision) {
    case "gps":
      how = `Ubicado por GPS en ${coords}`;
      break;
    case "address":
      how = `Ubicado por dirección en ${coords}`;
      break;
    case "barrio":
      how = "Ubicado en el centro del barrio (sin GPS)";
      break;
    default:
      how = "El reporte no trae ubicación";
  }
  return (
    <p className="mt-1 text-sm">
      <span className="font-bold">
        {detail.barrio ?? (hasPoint ? "Barrio sin identificar" : "Sin ubicación")}
      </span>
      <span className="block text-xs tabular-nums text-tinta-suave">{how}</span>
    </p>
  );
}
