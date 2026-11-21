/** Utilidades puras del despacho (specs/002 US1): capas del mapa y estado "listo para cerrar". */
import type { DispatchOut, IncidentDetail, ResourceOut, ResourceStatus } from "@/lib/labels";

type FC = GeoJSON.FeatureCollection;

export function newClientUuid(): string {
  return crypto.randomUUID();
}

export function isActive(status: DispatchOut["status"]): boolean {
  return status === "en_camino" || status === "en_sitio";
}

/** Atención finalizada y sin despachos activos: el operador decide si cierra (FR-011). */
export function readyToClose(detail: Pick<IncidentDetail, "status" | "dispatches">): boolean {
  const dispatches = detail.dispatches ?? [];
  return (
    detail.status === "verificado" &&
    dispatches.some((d) => d.status === "finalizado") &&
    !dispatches.some((d) => isActive(d.status))
  );
}

export interface ResourcePoint {
  id: string;
  code: string;
  label: string;
  status: ResourceStatus;
  lat: number;
  lon: number;
}

export function toPoint(r: ResourceOut): ResourcePoint {
  return { id: r.id, code: r.code, label: r.label, status: r.status, lat: r.lat, lon: r.lon };
}

export function resourcesToGeoJSON(resources: Iterable<ResourcePoint>): FC {
  return {
    type: "FeatureCollection",
    features: Array.from(resources, (r) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [r.lon, r.lat] },
      properties: { id: r.id, code: r.code, label: r.label, status: r.status },
    })),
  };
}

/** Recorridos de despachos activos: línea por los puntos de paso en orden de hora. */
export function trailsToGeoJSON(trails: Map<string, [number, number][]>): FC {
  return {
    type: "FeatureCollection",
    features: Array.from(trails.entries())
      .filter(([, coords]) => coords.length >= 2)
      .map(([id, coords]) => ({
        type: "Feature" as const,
        geometry: { type: "LineString" as const, coordinates: coords },
        properties: { dispatch_id: id },
      })),
  };
}
