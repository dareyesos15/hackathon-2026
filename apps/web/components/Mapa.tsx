"use client";
/**
 * Mapa de daños (FR-022): fondo offline con barrios SIMULADOS (sin teselas en línea),
 * capa por manzana con concentración de reportes y círculos de incidentes
 * (color = nivel de triaje, tamaño = número de reportes).
 */
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent } from "maplibre-gl";
import type { IncidentSummary } from "@/lib/labels";
import { TRIAGE_COLOR } from "@/lib/labels";

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
}

export function Mapa({ incidents, barrios, manzanas, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelect);
  const latest = useRef({ incidents, barrios, manzanas, selectedId });

  useEffect(() => {
    onSelectRef.current = onSelect;
    latest.current = { incidents, barrios, manzanas, selectedId };
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
        map.on("click", "incidentes", (e: MapLayerMouseEvent) => {
          const id = e.features?.[0]?.properties?.id;
          if (typeof id === "string") onSelectRef.current(id);
        });
        map.on("mouseenter", "incidentes", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "incidentes", () => (map.getCanvas().style.cursor = ""));
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

  return <div ref={container} className="h-full min-h-[420px] w-full rounded-xl" />;
}
