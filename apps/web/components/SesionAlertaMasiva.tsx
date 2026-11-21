"use client";
/**
 * Barra de sesión del tablero PMU: operación ordinaria, incidentes sin asignar o la sesión de una
 * alerta masiva de toda la ciudad (puede haber varias activas). Desde aquí se activa una alerta
 * masiva y se abre su reporte (preliminar o final).
 */
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import {
  MASS_EVENT_LABEL,
  ORDINARY,
  UNASSIGNED,
  type MassAlertEvent,
  type MassAlertOut,
  type SessionId,
} from "@/lib/massAlerts";

const EVENTS = Object.keys(MASS_EVENT_LABEL) as MassAlertEvent[];

function reportHref(id: string) {
  return `/pmu/alerta-masiva/?id=${id}`;
}

export function FormularioActivacion({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (alert: MassAlertOut) => void;
}) {
  const [eventType, setEventType] = useState<MassAlertEvent>("sismo");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [official, setOfficial] = useState(true);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/v1/mass-alerts", {
      body: {
        title: title.trim() || `${MASS_EVENT_LABEL[eventType]} · Manizales`,
        event_type: eventType,
        description: description.trim() || null,
        official_alert: official,
        message: message.trim() || null,
      },
    });
    setBusy(false);
    if (data) onCreated(data);
    else setError((err as { detail?: string } | undefined)?.detail ?? "No se pudo activar");
  }

  return (
    <form
      onSubmit={submit}
      className="grid gap-3 border-t border-senal/30 bg-senal-fondo px-4 py-3 text-sm md:grid-cols-[180px_1fr_1fr]"
    >
      <label className="flex flex-col gap-1">
        <span className="font-medium">Evento</span>
        <select
          value={eventType}
          onChange={(e) => setEventType(e.target.value as MassAlertEvent)}
          className="rounded border border-linea bg-white px-2 py-1"
        >
          {EVENTS.map((ev) => (
            <option key={ev} value={ev}>
              {MASS_EVENT_LABEL[ev]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Título</span>
        <input
          value={title}
          maxLength={120}
          placeholder={`${MASS_EVENT_LABEL[eventType]} · Manizales`}
          onChange={(e) => setTitle(e.target.value)}
          className="rounded border border-linea bg-white px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Descripción (opcional)</span>
        <input
          value={description}
          maxLength={1000}
          placeholder="Magnitud, fuente (SGC), hora…"
          onChange={(e) => setDescription(e.target.value)}
          className="rounded border border-linea bg-white px-2 py-1"
        />
      </label>
      <div className="flex flex-col gap-2 md:col-span-3">
        <label className="flex items-start gap-2">
          <input
            type="checkbox"
            className="mt-1"
            checked={official}
            onChange={(e) => setOfficial(e.target.checked)}
          />
          <span>
            Crear también el borrador de alerta oficial para todos los barrios
            <span className="block text-xs text-tinta-suave">
              Queda en la bandeja de Alertas; solo el COE la aprueba y la emite (EMRE tarea 5.5).
            </span>
          </span>
        </label>
        {official && (
          <input
            value={message}
            maxLength={160}
            placeholder="Mensaje a la ciudadanía (opcional; si se deja vacío se usa uno estándar)"
            onChange={(e) => setMessage(e.target.value)}
            className="rounded border border-linea bg-white px-2 py-1"
          />
        )}
        <p className="text-xs text-tinta-suave">
          Puede haber varias alertas masivas activas a la vez. Mientras haya alguna, los incidentes
          nuevos quedan sin asignar hasta que el PMU o el COE los asigne en la Gestión de
          incidentes. La alerta se cierra a mano y entonces se genera el reporte final.
        </p>
        {error && <p className="font-medium text-senal">{error}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-senal px-3 py-1.5 font-bold text-white hover:bg-[#b51723] disabled:opacity-60"
          >
            {busy ? "Activando…" : "Activar para toda la ciudad"}
          </button>
          <button type="button" onClick={onCancel} className="rounded px-3 py-1.5 text-tinta-suave">
            Cancelar
          </button>
        </div>
      </div>
    </form>
  );
}

export function SesionAlertaMasiva({
  items,
  active,
  unassignedCount,
  session,
  onSession,
}: {
  items: MassAlertOut[];
  active: MassAlertOut[];
  unassignedCount: number;
  session: SessionId;
  onSession: (s: SessionId) => void;
}) {
  const [creating, setCreating] = useState(false);
  const viewing = items.find((a) => a.id === session) ?? null;
  const closed = items.filter((a) => a.status !== "activa");

  return (
    <div className="border-b border-linea">
      {active.length > 0 && (
        <div className="flex flex-col gap-1 bg-senal px-4 py-2 text-white">
          {active.map((a) => (
            <div key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1">
              <span className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide">
                <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-white motion-reduce:animate-none" />
                Alerta masiva
              </span>
              <span className="text-sm">
                {a.title} · {MASS_EVENT_LABEL[a.event_type]} · desde {formatDateTime(a.started_at)}
              </span>
              <span className="rounded-sm bg-white/15 px-2 py-0.5 text-sm tabular-nums">
                {a.incidents_closed}/{a.incidents_total} incidentes cerrados
              </span>
              <span className="ml-auto flex gap-2 text-sm">
                {session !== a.id && (
                  <button
                    type="button"
                    onClick={() => onSession(a.id)}
                    className="rounded bg-white px-2 py-1 font-bold text-senal"
                  >
                    Ver sesión
                  </button>
                )}
                <Link
                  href={reportHref(a.id)}
                  className="rounded bg-white/15 px-2 py-1 font-medium hover:bg-white/25"
                >
                  Reporte preliminar
                </Link>
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2 bg-white px-4 py-1.5 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-tinta-suave">Sesión del tablero</span>
          <select
            value={session}
            onChange={(e) => onSession(e.target.value)}
            className="rounded border border-linea bg-white px-2 py-0.5"
          >
            <option value={ORDINARY}>Operación ordinaria</option>
            {(active.length > 0 || unassignedCount > 0) && (
              <option value={UNASSIGNED}>Sin asignar ({unassignedCount})</option>
            )}
            {active.length > 0 && (
              <optgroup label="Alertas masivas activas">
                {active.map((a) => (
                  <option key={a.id} value={a.id}>
                    ● {a.title}
                  </option>
                ))}
              </optgroup>
            )}
            {closed.length > 0 && (
              <optgroup label="Alertas masivas cerradas">
                {closed.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </label>
        {unassignedCount > 0 && (
          <Link
            href="/pmu/gestion/"
            className="rounded-sm bg-[#ffd27a] px-2 py-0.5 font-bold text-tinta"
          >
            {unassignedCount} sin asignar · asignar
          </Link>
        )}
        {viewing && viewing.status === "resuelta" && (
          <span className="flex items-center gap-2">
            <span className="rounded-sm bg-verificado/10 px-2 py-0.5 font-medium text-verificado">
              Cerrada {viewing.resolved_at ? formatDateTime(viewing.resolved_at) : ""}
            </span>
            <Link
              href={reportHref(viewing.id)}
              className="font-medium underline underline-offset-4"
            >
              Ver reporte final
            </Link>
          </span>
        )}
        {session !== ORDINARY && (
          <span className="text-xs text-tinta-suave">
            El mapa, el triaje, la cascada y las zonas muestran solo esta sesión.
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          <Link href="/pmu/gestion/" className="font-medium underline underline-offset-4">
            Gestión de incidentes
          </Link>
          {!creating && (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="rounded border border-senal px-3 py-1 font-bold text-senal hover:bg-senal-fondo"
            >
              Activar alerta masiva
            </button>
          )}
        </span>
      </div>
      {creating && (
        <FormularioActivacion
          onCancel={() => setCreating(false)}
          onCreated={(alert) => {
            setCreating(false);
            onSession(alert.id);
          }}
        />
      )}
    </div>
  );
}
