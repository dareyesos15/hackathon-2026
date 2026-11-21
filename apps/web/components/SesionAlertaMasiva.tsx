"use client";
/**
 * Barra de sesión del tablero PMU: operación ordinaria o la sesión de una alerta masiva de toda
 * la ciudad. Desde aquí se activa la alerta masiva y se abre su reporte (preliminar o final).
 */
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import {
  MASS_EVENT_LABEL,
  ORDINARY,
  type MassAlertEvent,
  type MassAlertOut,
  type SessionId,
} from "@/lib/massAlerts";

const EVENTS = Object.keys(MASS_EVENT_LABEL) as MassAlertEvent[];

function reportHref(id: string) {
  return `/pmu/alerta-masiva/?id=${id}`;
}

function FormularioActivacion({
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
          Al activarla, todo reporte nuevo queda en la sesión de esta alerta (triaje, cascada y
          zonas propios). Se resuelve sola cuando se cierran todos sus incidentes y entonces se
          genera el reporte final.
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
  session,
  onSession,
}: {
  items: MassAlertOut[];
  active: MassAlertOut | null;
  session: SessionId;
  onSession: (s: SessionId) => void;
}) {
  const [creating, setCreating] = useState(false);
  const viewing = session === ORDINARY ? null : (items.find((a) => a.id === session) ?? null);

  return (
    <div className="border-b border-linea">
      {active && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 bg-senal px-4 py-2 text-white">
          <span className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide">
            <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-white motion-reduce:animate-none" />
            Alerta masiva activa
          </span>
          <span className="text-sm">
            {active.title} · {MASS_EVENT_LABEL[active.event_type]} · desde{" "}
            {formatDateTime(active.started_at)}
          </span>
          <span className="rounded-sm bg-white/15 px-2 py-0.5 text-sm tabular-nums">
            {active.incidents_closed}/{active.incidents_total} incidentes resueltos
          </span>
          <span className="ml-auto flex gap-2 text-sm">
            {session !== active.id ? (
              <button
                type="button"
                onClick={() => onSession(active.id)}
                className="rounded bg-white px-2 py-1 font-bold text-senal"
              >
                Ver sesión de la alerta
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onSession(ORDINARY)}
                className="rounded bg-white/15 px-2 py-1 font-medium hover:bg-white/25"
              >
                Ver operación ordinaria
              </button>
            )}
            <Link
              href={reportHref(active.id)}
              className="rounded bg-white/15 px-2 py-1 font-medium hover:bg-white/25"
            >
              Reporte preliminar
            </Link>
          </span>
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
            {items.map((a) => (
              <option key={a.id} value={a.id}>
                {a.status === "activa" ? "● " : ""}
                {a.title} ({a.status === "activa" ? "activa" : "resuelta"})
              </option>
            ))}
          </select>
        </label>
        {viewing && viewing.status === "resuelta" && (
          <span className="flex items-center gap-2">
            <span className="rounded-sm bg-verificado/10 px-2 py-0.5 font-medium text-verificado">
              Resuelta {viewing.resolved_at ? formatDateTime(viewing.resolved_at) : ""}
            </span>
            <Link
              href={reportHref(viewing.id)}
              className="font-medium underline underline-offset-4"
            >
              Ver reporte final
            </Link>
          </span>
        )}
        {viewing && (
          <span className="text-xs text-tinta-suave">
            El mapa, el triaje, la cascada y las zonas muestran solo esta alerta.
          </span>
        )}
        {!active && !creating && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="ml-auto rounded border border-senal px-3 py-1 font-bold text-senal hover:bg-senal-fondo"
          >
            Activar alerta masiva
          </button>
        )}
      </div>
      {creating && !active && (
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
