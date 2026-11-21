/** Utilidades de alertas (specs/002 US2): área, largo para SMS y precarga desde un incidente. */
import type { AlertAreaIn, AlertChannel, AlertType, Category, IncidentDetail } from "@/lib/labels";

export const SMS_MAX = 160;

export interface CircleDraft {
  lat: number;
  lon: number;
  radius_m: number;
}

export interface AlertDraft {
  type: AlertType;
  barrios: string[];
  circle: CircleDraft | null;
  message: string;
  channels: AlertChannel[];
  origin_incident_id?: string | null;
  origin_manzana_id?: string | null;
}

export function buildArea(draft: Pick<AlertDraft, "barrios" | "circle">): AlertAreaIn | null {
  if (draft.circle) return { circle: draft.circle };
  if (draft.barrios.length > 0) return { barrios: draft.barrios };
  return null;
}

export function smsOverflow(message: string, channels: AlertChannel[]): number {
  if (!channels.includes("sms_cuadrillas")) return 0;
  return Math.max(0, message.trim().length - SMS_MAX);
}

const TYPE_BY_CATEGORY: Partial<Record<Category, AlertType>> = {
  deslizamiento: "deslizamiento",
  personas_atrapadas: "evacuacion",
  colapso_estructura: "evacuacion",
  incendio: "evacuacion",
  fuga_gas: "evacuacion",
  dano_estructural: "evacuacion",
  servicios_caidos: "servicios_publicos",
  sismo_sentido: "sismo_replica",
  rumor_informacion: "sismo_replica",
};

export function draftFromIncident(incident: IncidentDetail): AlertDraft {
  const circle =
    incident.lat !== null && incident.lon !== null
      ? { lat: incident.lat, lon: incident.lon, radius_m: 300 }
      : null;
  return {
    type: TYPE_BY_CATEGORY[incident.category] ?? "informacion_general",
    barrios: circle || !incident.barrio ? [] : [incident.barrio],
    circle,
    message: "",
    channels: ["tablero", "mapa_publico"],
    origin_incident_id: incident.id,
  };
}

export function draftFromManzana(props: {
  manzana_id: string;
  lat: number;
  lon: number;
}): AlertDraft {
  return {
    type: "deslizamiento",
    barrios: [],
    circle: { lat: props.lat, lon: props.lon, radius_m: 250 },
    message: "",
    channels: ["tablero", "mapa_publico", "sms_cuadrillas"],
    origin_manzana_id: props.manzana_id,
  };
}

export function emptyDraft(): AlertDraft {
  return {
    type: "informacion_general",
    barrios: [],
    circle: null,
    message: "",
    channels: ["tablero", "mapa_publico"],
  };
}

/** Polígono aproximado del círculo para previsualizarlo en el mapa (la API es la autoridad). */
export function circlePreview(c: CircleDraft): GeoJSON.FeatureCollection {
  const coords: [number, number][] = [];
  for (let i = 0; i <= 32; i++) {
    const a = (i / 32) * 2 * Math.PI;
    coords.push([
      c.lon + (c.radius_m / (111320 * Math.cos((c.lat * Math.PI) / 180))) * Math.cos(a),
      c.lat + (c.radius_m / 110540) * Math.sin(a),
    ]);
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [coords] },
        properties: { preview: true },
      },
    ],
  };
}
