"use client";
/**
 * Mapa de daños (FR-022): fondo offline con barrios SIMULADOS (sin teselas en línea),
 * capa por manzana con concentración de reportes y círculos de incidentes
 * (color = nivel de triaje, tamaño = número de reportes).
 * specs/002: recursos y recorridos (US1), áreas de alertas vigentes y selección de un punto
 * (US2), capa de efectos en cascada por manzana (US3). Todas las capas nuevas son opcionales.
 */
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MLMap, MapMouseEvent } from "maplibre-gl";
import type { IncidentSummary } from "@/lib/labels";
import {
  CASCADE_LEVEL_COLOR,
  RESOURCE_STATUS_COLOR,
  RESOURCE_STATUS_LABEL,
  TRIAGE_COLOR,
} from "@/lib/labels";

type FeatureCollection = GeoJSON.FeatureCollection;

const CENTER: [number, number] = [-75.5, 5.062];
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

export function incidentsToGeoJSON(
  incidents: IncidentSummary[],
  selectedId: string | null,
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: incidents
      .filter((i) => i.lat !== null && i.lon !== null)
      .map((i) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [i.lon as number, i.lat as number] },
        properties: {
          id: i.id,
          triage: i.triage_level,
          reports: i.report_count,
          fake: i.trust_label === "posible_falso",
          selected: i.id === selectedId,
        },
      })),
  };
}

interface Props {
  incidents: IncidentSummary[];
  barrios: FeatureCollection | null;
  manzanas: FeatureCollection | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Recursos (puntos) y recorridos (líneas) de despachos activos. */
  resources?: FeatureCollection | null;
  trails?: FeatureCollection | null;
  /** Áreas de alertas vigentes (polígonos). */
  alertAreas?: FeatureCollection | null;
  /** Capa de cascada por manzana; `null` la oculta. */
  cascade?: FeatureCollection | null;
  onCascadeSelect?: (properties: Record<string, unknown>) => void;
  /** Si está definido, un clic en el mapa entrega el punto (p. ej. centro de un área). */
  onMapClick?: (lat: number, lon: number) => void;
}

type Extra = "resources" | "trails" | "alertAreas" | "cascade";
const EXTRA_SOURCES: Record<Extra, string> = {
  resources: "recursos",
  trails: "recorridos",
  alertAreas: "alertas",
  cascade: "cascada",
};

export function Mapa({
  incidents,
  barrios,
  manzanas,
  selectedId,
  onSelect,
  resources = null,
  trails = null,
  alertAreas = null,
  cascade = null,
  onCascadeSelect,
  onMapClick,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelect);
  const onCascadeRef = useRef(onCascadeSelect);
  const onMapClickRef = useRef(onMapClick);
  const latest = useRef({ incidents, barrios, manzanas, selectedId });
  const extras = useRef<Record<Extra, FeatureCollection | null>>({
    resources,
    trails,
    alertAreas,
    cascade,
  });

  useEffect(() => {
    onSelectRef.current = onSelect;
    onCascadeRef.current = onCascadeSelect;
    onMapClickRef.current = onMapClick;
    latest.current = { incidents, barrios, manzanas, selectedId };
    extras.current = { resources, trails, alertAreas, cascade };
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const maplibre = await import("maplibre-gl");
      maplibre.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");
      if (cancelled || !container.current) return;
      const map = new maplibre.Map({
        container: container.current,
        center: CENTER,
        zoom: 13.2,
        attributionControl: { compact: true, customAttribution: "Geografía SIMULADA · Dacora" },
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "fondo", type: "background", paint: { "background-color": "#e2e8f0" } }],
        },
      });
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      mapRef.current = map;

      map.on("load", () => {
        map.addSource("barrios", { type: "geojson", data: latest.current.barrios ?? EMPTY });
        map.addSource("manzanas", { type: "geojson", data: latest.current.manzanas ?? EMPTY });
        map.addSource("incidentes", {
          type: "geojson",
          data: incidentsToGeoJSON(latest.current.incidents, latest.current.selectedId),
        });
        map.addLayer({
          id: "barrios-relleno",
          type: "fill",
          source: "barrios",
          paint: { "fill-color": "#f8fafc", "fill-opacity": 0.9 },
        });
        map.addLayer({
          id: "barrios-borde",
          type: "line",
          source: "barrios",
          paint: { "line-color": "#94a3b8", "line-width": 1 },
        });
        map.addLayer({
          id: "manzanas-calor",
          type: "fill",
          source: "manzanas",
          paint: {
            // Conteo nulo = oculto por k-anonimato (vista pública): gris neutro.
            "fill-color": [
              "case",
              ["==", ["get", "report_count"], null],
              "#cbd5e1",
              [
                "interpolate",
                ["linear"],
                ["get", "report_count"],
                1,
                "#fde68a",
                4,
                "#fb923c",
                10,
                "#b91c1c",
              ],
            ],
            "fill-opacity": 0.55,
          },
        });
        for (const [key, id] of Object.entries(EXTRA_SOURCES) as [Extra, string][]) {
          map.addSource(id, { type: "geojson", data: extras.current[key] ?? EMPTY });
        }
        map.addLayer({
          id: "cascada-relleno",
          type: "fill",
          source: "cascada",
          paint: {
            "fill-color": [
              "match",
              ["get", "level"],
              "muy_alto",
              CASCADE_LEVEL_COLOR.muy_alto,
              "alto",
              CASCADE_LEVEL_COLOR.alto,
              "medio",
              CASCADE_LEVEL_COLOR.medio,
              CASCADE_LEVEL_COLOR.bajo,
            ],
            "fill-opacity": 0.6,
          },
        });
        map.addLayer({
          id: "alertas-relleno",
          type: "fill",
          source: "alertas",
          paint: { "fill-color": "#f59e0b", "fill-opacity": 0.18 },
        });
        map.addLayer({
          id: "alertas-borde",
          type: "line",
          source: "alertas",
          paint: { "line-color": "#b45309", "line-width": 2.5, "line-dasharray": [2, 1] },
        });
        map.addLayer({
          id: "recorridos",
          type: "line",
          source: "recorridos",
          paint: { "line-color": "#7c3aed", "line-width": 3, "line-dasharray": [1, 1] },
        });
        map.addLayer({
          id: "incidentes",
          type: "circle",
          source: "incidentes",
          paint: {
            "circle-color": [
              "match",
              ["get", "triage"],
              "critico",
              TRIAGE_COLOR.critico,
              "alto",
              TRIAGE_COLOR.alto,
              "medio",
              TRIAGE_COLOR.medio,
              TRIAGE_COLOR.bajo,
            ],
            "circle-radius": ["interpolate", ["linear"], ["get", "reports"], 1, 6, 4, 10, 12, 18],
            "circle-opacity": ["case", ["get", "fake"], 0.35, 0.85],
            "circle-stroke-width": ["case", ["get", "selected"], 4, 1.5],
            "circle-stroke-color": ["case", ["get", "selected"], "#0f172a", "#ffffff"],
          },
        });
        map.addLayer({
          id: "recursos",
          type: "circle",
          source: "recursos",
          paint: {
            "circle-color": [
              "match",
              ["get", "status"],
              "en_camino",
              RESOURCE_STATUS_COLOR.en_camino,
              "en_sitio",
              RESOURCE_STATUS_COLOR.en_sitio,
              "fuera_de_servicio",
              RESOURCE_STATUS_COLOR.fuera_de_servicio,
              RESOURCE_STATUS_COLOR.disponible,
            ],
            "circle-radius": ["case", ["==", ["get", "status"], "disponible"], 4, 7],
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          },
        });
        map.on("click", (e: MapMouseEvent) => {
          if (onMapClickRef.current) {
            onMapClickRef.current(e.lngLat.lat, e.lngLat.lng);
            return;
          }
          const layers = ["incidentes", "recursos", "cascada-relleno"].filter((l) =>
            map.getLayer(l),
          );
          const [hit] = map.queryRenderedFeatures(e.point, { layers });
          if (!hit) return;
          const props = hit.properties ?? {};
          if (hit.layer.id === "incidentes" && typeof props.id === "string") {
            onSelectRef.current(props.id);
          } else if (hit.layer.id === "recursos") {
            new maplibre.Popup({ closeButton: false })
              .setLngLat(e.lngLat)
              .setText(
                `${props.label} · ${RESOURCE_STATUS_LABEL[props.status as keyof typeof RESOURCE_STATUS_LABEL] ?? props.status} (SIMULADO)`,
              )
              .addTo(map);
          } else if (hit.layer.id === "cascada-relleno") {
            onCascadeRef.current?.(props);
          }
        });
        for (const layer of ["incidentes", "recursos"]) {
          map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
          map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
        }
        ready.current = true;
      });
    })();
    return () => {
      cancelled = true;
      ready.current = false;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready.current || !mapRef.current) return;
    mapRef.current
      .getSource<GeoJSONSource>("incidentes")
      ?.setData(incidentsToGeoJSON(incidents, selectedId));
  }, [incidents, selectedId]);

  useEffect(() => {
    if (!ready.current || !mapRef.current) return;
    if (barrios) mapRef.current.getSource<GeoJSONSource>("barrios")?.setData(barrios);
    if (manzanas) mapRef.current.getSource<GeoJSONSource>("manzanas")?.setData(manzanas);
  }, [barrios, manzanas]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready.current || !map) return;
    const data: Record<Extra, FeatureCollection | null> = {
      resources,
      trails,
      alertAreas,
      cascade,
    };
    for (const [key, id] of Object.entries(EXTRA_SOURCES) as [Extra, string][]) {
      map.getSource<GeoJSONSource>(id)?.setData(data[key] ?? EMPTY);
    }
  }, [resources, trails, alertAreas, cascade]);

  useEffect(() => {
    const map = mapRef.current;
    if (map) map.getCanvas().style.cursor = onMapClick ? "crosshair" : "";
  }, [onMapClick]);

  return <div ref={container} className="h-full min-h-[420px] w-full rounded-xl" />;
}
