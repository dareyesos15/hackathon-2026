"use client";
/** Alertas oficiales vigentes, destacadas en el tablero del PMU y en el mapa público (US2). */
import { formatTime } from "@/lib/format";
import { ALERT_TYPE_LABEL, type AlertType } from "@/lib/labels";

export interface ActiveAlert {
  id: string;
  type: AlertType;
  message: string;
  emitted_at: string | null;
}

export function alertsFromGeoJSON(fc: GeoJSON.FeatureCollection | null): ActiveAlert[] {
  return (fc?.features ?? []).map((f) => f.properties as ActiveAlert);
}

export function AvisoAlerta({ alerts }: { alerts: ActiveAlert[] }) {
  if (alerts.length === 0) return null;
  return (
    <div className="flex flex-col gap-1" role="alert">
      {alerts.map((a) => (
        <div
          key={a.id}
          className="flex flex-wrap items-center gap-2 rounded-lg bg-red-700 px-3 py-2 text-sm text-white shadow"
        >
          <span className="rounded bg-white px-1.5 text-[10px] font-bold text-red-700">
            ALERTA OFICIAL · COE
          </span>
          <span className="font-semibold">{ALERT_TYPE_LABEL[a.type]}</span>
          <span className="flex-1">{a.message}</span>
          {a.emitted_at && (
            <span className="text-xs text-red-100">emitida {formatTime(a.emitted_at)}</span>
          )}
        </div>
      ))}
    </div>
  );
}
