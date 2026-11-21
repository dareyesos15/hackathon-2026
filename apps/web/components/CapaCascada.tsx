"use client";
/**
 * Capa de efectos en cascada (specs/002 US3): interruptor, leyenda, control de lluvia SIMULADA,
 * desglose de la manzana elegida y salida a una alerta preventiva (que igual aprueba el COE).
 * Es solo una sugerencia: no despacha ni alerta por sí sola (FR-031).
 */
import { useState } from "react";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt, formatNumber } from "@/lib/format";
import {
  CASCADE_FACTOR_LABEL,
  CASCADE_LEVEL_COLOR,
  CASCADE_LEVEL_LABEL,
  CASCADE_LEVEL_ORDER,
  type CascadeLevel,
} from "@/lib/labels";
import { EtiquetaSimulado } from "./EtiquetaSimulado";

export type CascadeLayer = GeoJSON.FeatureCollection & {
  cutoff_at?: string;
  scenario_clock?: string | null;
  rain_mm_3h?: number | null;
  model_version?: string;
};

interface Factor {
  puntos: number;
  max: number;
  detalle: string;
}

export interface CascadeSelection {
  manzana_id: string;
  barrio: string;
  level: CascadeLevel;
  score: number;
  breakdown: Record<string, Factor>;
  model_version: string;
  lat: number;
  lon: number;
}

/** Propiedades de una manzana tocada en el mapa (MapLibre serializa los objetos anidados). */
export function selectionFrom(
  props: Record<string, unknown>,
  layer: CascadeLayer | null,
): CascadeSelection | null {
  const id = String(props.manzana_id ?? "");
  const feature = layer?.features.find((f) => f.properties?.manzana_id === id);
  if (!feature) return null;
  const p = feature.properties as Omit<CascadeSelection, "lat" | "lon">;
  const ring = (() => {
    const g = feature.geometry;
    if (g.type === "Polygon") return g.coordinates[0];
    if (g.type === "MultiPolygon") return g.coordinates[0][0];
    return [];
  })();
  const n = Math.max(1, ring.length);
  const lon = ring.reduce((s, c) => s + c[0], 0) / n;
  const lat = ring.reduce((s, c) => s + c[1], 0) / n;
  const breakdown =
    typeof p.breakdown === "string"
      ? (JSON.parse(p.breakdown) as Record<string, Factor>)
      : p.breakdown;
  return { ...p, breakdown, lat, lon };
}

interface Props {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
  layer: CascadeLayer | null;
  selected: CascadeSelection | null;
  onCreateAlert?: (selection: CascadeSelection) => void;
  /** Solo el PMU y el COE publican lecturas de lluvia SIMULADA. */
  canControlRain?: boolean;
  /** Sin conexión: se muestra la última predicción guardada en el dispositivo. */
  offline?: boolean;
  savedAt?: string | null;
}

export function CapaCascada({
  enabled,
  onToggle,
  layer,
  selected,
  onCreateAlert,
  canControlRain = true,
  offline = false,
  savedAt = null,
}: Props) {
  const [rain, setRain] = useState<number>(layer?.rain_mm_3h ?? 0);
  const [busy, setBusy] = useState(false);

  async function publishRain(value: number) {
    setBusy(true);
    await api.POST("/api/v1/sensors/rain", {
      body: { mm_3h: value, station_code: "LLUVIA-URB-01" },
    });
    setBusy(false);
  }

  const counts = CASCADE_LEVEL_ORDER.reduce(
    (acc, level) => ({
      ...acc,
      [level]: (layer?.features ?? []).filter((f) => f.properties?.level === level).length,
    }),
    {} as Record<CascadeLevel, number>,
  );

  return (
    <section className="flex flex-col gap-3 rounded-lg bg-white p-3 text-sm shadow-sm">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 font-semibold">
          <input type="checkbox" checked={enabled} onChange={(e) => onToggle(e.target.checked)} />
          Efectos en cascada
        </label>
        <EtiquetaSimulado />
      </div>
      <p className="text-[11px] text-tinta-suave">
        Riesgo de deslizamiento o colapso secundario por manzana: pendiente, lluvia, intensidad
        sísmica y reportes cercanos. Sugerencia; decide el PMU.
      </p>

      <ul className="grid grid-cols-2 gap-1 text-xs">
        {CASCADE_LEVEL_ORDER.map((level) => (
          <li key={level} className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-5 rounded-sm border border-linea"
              style={{ background: CASCADE_LEVEL_COLOR[level] }}
            />
            {CASCADE_LEVEL_LABEL[level]}
            {enabled && <span className="text-tinta-suave">({formatInt(counts[level])})</span>}
          </li>
        ))}
      </ul>

      {enabled && offline && (
        <p className="rounded bg-amber-100 p-2 text-xs text-amber-900">
          Sin conexión: se muestra la última predicción recibida
          {savedAt ? ` (${formatDateTime(savedAt)})` : ""}. Se recalcula sola al volver la conexión.
        </p>
      )}
      {enabled && offline && !layer && (
        <p className="text-xs text-tinta-suave">
          Aún no hay una predicción guardada en este dispositivo.
        </p>
      )}

      {!canControlRain && layer && (
        <p className="text-xs text-tinta-suave">
          Lluvia acumulada en 3 h: {formatInt(layer.rain_mm_3h ?? 0)} mm (estación LLUVIA-URB-01,
          SIMULADA)
        </p>
      )}

      {canControlRain && (
        <label className="flex flex-col gap-1 text-xs">
          Lluvia acumulada en 3 h · estación LLUVIA-URB-01 (SIMULADA, patente NC2022/0005821)
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={60}
              step={5}
              value={rain}
              disabled={busy || offline}
              onChange={(e) => setRain(Number(e.target.value))}
              onMouseUp={() => publishRain(rain)}
              onTouchEnd={() => publishRain(rain)}
              onKeyUp={() => publishRain(rain)}
              className="flex-1"
            />
            <span className="w-14 text-right tabular-nums">{formatInt(rain)} mm</span>
          </div>
        </label>
      )}

      {enabled && layer?.cutoff_at && (
        <p className="text-[10px] text-tinta-suave">
          Modelo {layer.model_version} · corte {formatDateTime(layer.cutoff_at)}
          {layer.scenario_clock && ` · reloj del escenario ${formatDateTime(layer.scenario_clock)}`}
        </p>
      )}

      {enabled && selected && (
        <div className="rounded border border-linea p-2">
          <div className="flex items-center justify-between">
            <span className="font-medium">
              {selected.barrio} · {selected.manzana_id}
            </span>
            <span
              className="rounded px-1.5 text-xs font-semibold"
              style={{
                background: CASCADE_LEVEL_COLOR[selected.level],
                color: selected.level === "muy_alto" ? "white" : "black",
              }}
            >
              {CASCADE_LEVEL_LABEL[selected.level]} · {formatNumber(selected.score, 0)}
            </span>
          </div>
          <ul className="mt-2 space-y-1">
            {Object.entries(selected.breakdown).map(([key, f]) => (
              <li key={key} className="text-xs">
                <div className="flex justify-between">
                  <span>{CASCADE_FACTOR_LABEL[key] ?? key}</span>
                  <span className="tabular-nums">
                    {formatNumber(f.puntos, 1)} / {f.max}
                  </span>
                </div>
                <div className="h-1.5 rounded bg-slate-100">
                  <div
                    className="h-1.5 rounded bg-slate-700"
                    style={{ width: `${Math.min(100, (f.puntos / f.max) * 100)}%` }}
                  />
                </div>
                <p className="text-[11px] text-tinta-suave">{f.detalle}</p>
              </li>
            ))}
          </ul>
          {onCreateAlert && (selected.level === "alto" || selected.level === "muy_alto") && (
            <button
              type="button"
              onClick={() => onCreateAlert(selected)}
              className="mt-2 w-full rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white"
            >
              Crear alerta preventiva
            </button>
          )}
        </div>
      )}
      {enabled && !selected && (
        <p className="text-xs text-tinta-suave">
          Toque una manzana en el mapa para ver el desglose.
        </p>
      )}
    </section>
  );
}
