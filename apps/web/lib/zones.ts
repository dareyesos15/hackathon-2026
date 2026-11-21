/** Sensor de zonas inseguras (patente UNAL NC2025/0015763, SIMULADO). specs/004. */
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type ZoneSensorOut = S["ZoneSensorOut"];
export type ZoneEventOut = S["ZoneEventOut"];
export type ZoneEventKind = S["ZoneEventKind"];
export type ZoneDetector = S["ZoneDetector"];

export const ZONE_EVENT_LABEL: Record<ZoneEventKind, string> = {
  intrusion: "Intrusión",
  acceso_autorizado: "Acceso autorizado (RFID)",
  bateria_baja: "Batería baja",
  manipulacion: "Manipulación del equipo",
};

export const ZONE_DETECTOR_LABEL: Record<ZoneDetector, string> = {
  ultrasonido: "ultrasonido",
  infrarrojo: "infrarrojo",
  ambos: "ultrasonido + infrarrojo",
};

export const ZONE_ALARM_KINDS: ZoneEventKind[] = ["intrusion", "manipulacion"];

export function isAlarm(e: ZoneEventOut): boolean {
  return ZONE_ALARM_KINDS.includes(e.kind) && !e.acknowledged_at;
}

/** Conos (polígonos) y posiciones (puntos) de los sensores para el mapa. */
export function zonesToGeoJSON(sensors: ZoneSensorOut[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: sensors.flatMap((s) => {
      const props = {
        id: s.id,
        code: s.code,
        label: s.label,
        alarm: s.open_alarms > 0,
        open_alarms: s.open_alarms,
        battery: s.battery_pct,
      };
      return [
        {
          type: "Feature" as const,
          geometry: { type: "Polygon" as const, coordinates: [s.cone] },
          properties: { ...props, part: "cone" },
        },
        {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
          properties: { ...props, part: "device" },
        },
      ];
    }),
  };
}
