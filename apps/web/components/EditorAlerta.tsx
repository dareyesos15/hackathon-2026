"use client";
/**
 * Editor de alertas (specs/002 US2): tipo, área (barrios o círculo marcado en el mapa), mensaje
 * con contador para SMS y canales. Guarda como borrador: solo el COE emite (EMRE tarea 5.5).
 * Si la API detecta señales de desinformación, pide confirmación explícita (FR-022).
 */
import { simulado } from "@/lib/env";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { SMS_MAX, buildArea, smsOverflow, type AlertDraft } from "@/lib/alerts";
import { formatInt } from "@/lib/format";
import {
  ALERT_CHANNEL_LABEL,
  ALERT_TYPE_LABEL,
  type AlertChannel,
  type AlertOut,
  type AlertType,
} from "@/lib/labels";

interface Props {
  draft: AlertDraft;
  /** Si existe, se edita ese borrador (PATCH con su versión). */
  existing?: AlertOut | null;
  barrioNames: string[];
  picking: boolean;
  onPickCenter: () => void;
  onChange: (draft: AlertDraft) => void;
  onClose: () => void;
  onSaved: (alert: AlertOut) => void;
}

interface ApiError {
  detail?: string;
  code?: string;
  signals?: string[];
}

const CHANNELS: AlertChannel[] = ["tablero", "mapa_publico", "sms_cuadrillas"];

export function EditorAlerta({
  draft,
  existing,
  barrioNames,
  picking,
  onPickCenter,
  onChange,
  onClose,
  onSaved,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [signals, setSignals] = useState<string[] | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const overflow = smsOverflow(draft.message, draft.channels);
  const area = buildArea(draft);
  const set = (patch: Partial<AlertDraft>) => onChange({ ...draft, ...patch });

  function toggleChannel(c: AlertChannel) {
    set({
      channels: draft.channels.includes(c)
        ? draft.channels.filter((x) => x !== c)
        : [...draft.channels, c],
    });
  }

  async function save() {
    if (!area) return;
    setBusy(true);
    setError(null);
    const result = existing
      ? await api.PATCH("/api/v1/alerts/{alert_id}", {
          params: { path: { alert_id: existing.id } },
          body: {
            version: existing.version,
            type: draft.type,
            area,
            message: draft.message.trim(),
            channels: draft.channels,
            confirm_misinformation: confirmed,
          },
        })
      : await api.POST("/api/v1/alerts", {
          body: {
            type: draft.type,
            area,
            message: draft.message.trim(),
            channels: draft.channels,
            origin_incident_id: draft.origin_incident_id ?? null,
            origin_manzana_id: draft.origin_manzana_id ?? null,
            confirm_misinformation: confirmed,
          },
        });
    setBusy(false);
    if (result.error) {
      const e = result.error as ApiError;
      if (e.code === "misinformation_confirmation_required") setSignals(e.signals ?? []);
      setError(e.detail ?? "No se pudo guardar la alerta");
      return;
    }
    if (result.data) onSaved(result.data);
  }

  return (
    <section className="flex flex-col gap-2 rounded-lg bg-white p-3 text-sm shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">
          {existing ? `Editar borrador (versión ${existing.version})` : "Nueva alerta (borrador)"}
        </h3>
        <button type="button" onClick={onClose} className="text-tinta-suave" aria-label="Cerrar">
          ✕
        </button>
      </div>

      <label className="flex flex-col gap-1 text-xs">
        Tipo
        <select
          className="rounded border border-linea bg-white px-2 py-1"
          value={draft.type}
          onChange={(e) => set({ type: e.target.value as AlertType })}
        >
          {(Object.keys(ALERT_TYPE_LABEL) as AlertType[]).map((t) => (
            <option key={t} value={t}>
              {ALERT_TYPE_LABEL[t]}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="flex flex-col gap-1 text-xs">
        <legend className="mb-1">Área</legend>
        {draft.circle ? (
          <div className="flex flex-wrap items-center gap-2 rounded bg-amber-50 p-2">
            <span>
              Círculo en {draft.circle.lat.toFixed(4)}, {draft.circle.lon.toFixed(4)}
            </span>
            <label className="flex items-center gap-1">
              radio
              <input
                type="number"
                min={100}
                max={3000}
                step={50}
                className="w-20 rounded border border-linea px-1"
                value={draft.circle.radius_m}
                onChange={(e) =>
                  set({
                    circle: draft.circle && {
                      ...draft.circle,
                      radius_m: Number(e.target.value),
                    },
                  })
                }
              />
              m
            </label>
            <button type="button" className="underline" onClick={() => set({ circle: null })}>
              Usar barrios
            </button>
          </div>
        ) : (
          <select
            multiple
            className="h-24 rounded border border-linea bg-white px-1"
            value={draft.barrios}
            onChange={(e) => set({ barrios: Array.from(e.target.selectedOptions, (o) => o.value) })}
          >
            {barrioNames.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          onClick={onPickCenter}
          className={`self-start rounded border px-2 py-0.5 ${
            picking ? "border-amber-600 bg-amber-100" : "border-linea"
          }`}
        >
          {picking ? "Haga clic en el mapa…" : "Marcar centro de un círculo en el mapa"}
        </button>
      </fieldset>

      <label className="flex flex-col gap-1 text-xs">
        Mensaje
        <textarea
          className="rounded border border-linea p-2"
          rows={3}
          maxLength={500}
          value={draft.message}
          onChange={(e) => {
            set({ message: e.target.value });
            setSignals(null);
            setConfirmed(false);
          }}
        />
        <span className={overflow > 0 ? "text-rose-700" : "text-tinta-suave"}>
          {formatInt(draft.message.trim().length)} caracteres
          {draft.channels.includes("sms_cuadrillas") &&
            ` · SMS máximo ${SMS_MAX}${overflow > 0 ? ` (sobran ${overflow})` : ""}`}
        </span>
      </label>

      <fieldset className="flex flex-col gap-1 text-xs">
        <legend className="mb-1">Canales</legend>
        {CHANNELS.map((c) => (
          <label key={c} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={draft.channels.includes(c)}
              onChange={() => toggleChannel(c)}
            />
            {ALERT_CHANNEL_LABEL[c]}
            {c === "sms_cuadrillas" && simulado(" (SIMULADO)")}
          </label>
        ))}
      </fieldset>

      {signals && (
        <div className="rounded bg-rose-50 p-2 text-xs text-rose-900">
          <p className="font-medium">Señales de desinformación: {signals.join(", ")}.</p>
          <p>
            El SGC no predice sismos ni réplicas. Corrija el mensaje o confirme que es correcto.
          </p>
          <label className="mt-1 flex items-center gap-2">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Confirmo que el mensaje es correcto (queda en la bitácora)
          </label>
        </div>
      )}

      <button
        type="button"
        disabled={
          busy ||
          !area ||
          !draft.message.trim() ||
          draft.channels.length === 0 ||
          overflow > 0 ||
          (signals !== null && !confirmed)
        }
        onClick={save}
        className="rounded bg-amber-600 px-3 py-1.5 font-medium text-white disabled:opacity-40"
      >
        {existing ? "Guardar cambios" : "Guardar borrador para el COE"}
      </button>
      {error && <p className="text-xs text-rose-700">{error}</p>}
    </section>
  );
}
