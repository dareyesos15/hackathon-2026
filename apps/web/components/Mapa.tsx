"use client";
/**
 * Mapa de daños (FR-022).
 * - Mapa base libre: OpenFreeMap (estilo «positron», datos © OpenStreetMap, sin clave).
 *   Si no hay internet en 3 s, cae al fondo offline con barrios SIMULADOS (Plan B).
 * - Capa por manzana con concentración de reportes.
 * - Incidentes como marcadores: color = nivel de triaje, pictograma = categoría,
 *   tamaño = número de reportes; anillo oscuro discontinuo = posible falso.
 */
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  GeoJSONSource,
  Map as MLMap,
  MapLayerMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import { drawMarker, markerImageId } from "@/lib/iconos";
import type { Category, IncidentSummary, TriageLevel } from "@/lib/labels";
import { CATEGORY_LABEL, TRIAGE_COLOR, TRIAGE_LABEL, TRIAGE_ORDER } from "@/lib/labels";
import { IconoCategoria } from "./IconoCategoria";

type FeatureCollection = GeoJSON.FeatureCollection;

const CENTER: [number, number] = [-75.5, 5.062];
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const BASEMAP_URL = "https://tiles.openfreemap.org/styles/positron";
const BASEMAP_TIMEOUT_MS = 3000;
const RANK: Record<TriageLevel, number> = { bajo: 0, medio: 1, alto: 2, critico: 3 };

const OFFLINE_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "fondo", type: "background", paint: { "background-color": "#ece6e4" } }],
};

type Basemap = "cargando" | "osm" | "offline";

/** Intenta el mapa base libre; sin red o si tarda, devuelve el estilo offline. */
async function loadBasemap(): Promise<{ style: StyleSpecification | string; kind: Basemap }> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return { style: OFFLINE_STYLE, kind: "offline" };
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), BASEMAP_TIMEOUT_MS);
  try {
    const res = await fetch(BASEMAP_URL, { signal: ctrl.signal });
    if (!res.ok) throw new Error(String(res.status));
    return { style: (await res.json()) as StyleSpecification, kind: "osm" };
  } catch {
    return { style: OFFLINE_STYLE, kind: "offline" };
  } finally {
    clearTimeout(timer);
  }
}

export function incidentsToGeoJSON(
  incidents: IncidentSummary[],
  selectedId: string | null,
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: incidents
      .filter((i) => i.lat !== null && i.lon !== null)
      .map((i) => {
        const fake = i.trust_label === "posible_falso";
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [i.lon as number, i.lat as number] },
          properties: {
            id: i.id,
            triage: i.triage_level,
            reports: i.report_count,
            fake,
            selected: i.id === selectedId,
            icon: markerImageId(i.category, i.triage_level, fake),
            rank: RANK[i.triage_level] + (i.id === selectedId ? 10 : 0),
          },
        };
      }),
  };
}

interface Props {
  incidents: IncidentSummary[];
  barrios: FeatureCollection | null;
  manzanas: FeatureCollection | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Leyenda de incidentes sobre el mapa (la vista pública no muestra incidentes). */
  leyenda?: boolean;
}

export function Mapa({
  incidents,
  barrios,
  manzanas,
  selectedId,
  onSelect,
  leyenda = true,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const onSelectRef = useRef(onSelect);
  const latest = useRef({ incidents, barrios, manzanas, selectedId });
  const [basemap, setBasemap] = useState<Basemap>("cargando");

  useEffect(() => {
    onSelectRef.current = onSelect;
    latest.current = { incidents, barrios, manzanas, selectedId };
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [maplibre, base] = await Promise.all([import("maplibre-gl"), loadBasemap()]);
      maplibre.setWorkerUrl("/vendor/maplibre-gl-worker.mjs");
      if (cancelled || !container.current) return;
      setBasemap(base.kind);
      const online = base.kind === "osm";
      const map = new maplibre.Map({
        container: container.current,
        center: CENTER,
        zoom: 13.4,
        attributionControl: {
          compact: true,
          customAttribution: "Barrios e incidentes SIMULADOS · Dacora",
        },
        style: base.style,
      });
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new maplibre.ScaleControl({ unit: "metric" }), "bottom-right");
      mapRef.current = map;

      // Marcadores generados a demanda: una imagen por categoría × triaje × falso.
      const ratio = Math.max(2, Math.ceil(window.devicePixelRatio || 1));
      const addMarker = (id: string) => {
        if (map.hasImage(id)) return;
        const img = drawMarker(id, ratio);
        if (img) map.addImage(id, img, { pixelRatio: ratio });
      };
      // Respaldo por si aparece una combinación nueva (p. ej. una categoría agregada a la API).
      map.on("styleimagemissing", (e) => {
        if (e.id.startsWith("inc:")) addMarker(e.id);
      });

      map.on("load", () => {
        // Todos los marcadores antes de la primera tesela: generarlos a demanda dejaba
        // teselas sin pintar cuando el escenario ya estaba cargado.
        for (const cat of Object.keys(CATEGORY_LABEL) as Category[]) {
          for (const level of TRIAGE_ORDER) {
            addMarker(markerImageId(cat, level, false));
            addMarker(markerImageId(cat, level, true));
          }
        }
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
          // Sobre el mapa real los barrios simulados solo se insinúan; offline hacen de fondo.
          paint: {
            "fill-color": online ? "#5c0f1b" : "#faf8f7",
            "fill-opacity": online ? 0.03 : 1,
          },
        });
        map.addLayer({
          id: "barrios-borde",
          type: "line",
          source: "barrios",
          paint: {
            "line-color": "#7d1a29",
            "line-opacity": online ? 0.35 : 0.5,
            "line-width": 1,
            "line-dasharray": [3, 2],
          },
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
              "#cfc6c4",
              [
                "interpolate",
                ["linear"],
                ["get", "report_count"],
                1,
                "#f9d5c6",
                4,
                "#ee6a2c",
                10,
                "#a3121f",
              ],
            ],
            "fill-opacity": 0.45,
          },
        });
        // Halo del incidente seleccionado, bajo el marcador.
        map.addLayer({
          id: "incidentes-halo",
          type: "circle",
          source: "incidentes",
          filter: ["==", ["get", "selected"], true],
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["get", "reports"], 1, 20, 4, 24, 12, 30],
            "circle-color": "#d21f2b",
            "circle-opacity": 0.18,
            "circle-stroke-color": "#5c0f1b",
            "circle-stroke-width": 2.5,
          },
        });
        map.addLayer({
          id: "incidentes",
          type: "symbol",
          source: "incidentes",
          layout: {
            "icon-image": ["get", "icon"],
            "icon-size": ["interpolate", ["linear"], ["get", "reports"], 1, 0.62, 4, 0.82, 12, 1.1],
            "icon-allow-overlap": true,
            "icon-ignore-placement": true,
            "symbol-sort-key": ["get", "rank"],
          },
          paint: { "icon-opacity": ["case", ["get", "fake"], 0.6, 1] },
        });
        map.on("click", "incidentes", (e: MapLayerMouseEvent) => {
          const id = e.features?.[0]?.properties?.id;
          if (typeof id === "string") onSelectRef.current(id);
        });
        map.on("mouseenter", "incidentes", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "incidentes", () => (map.getCanvas().style.cursor = ""));
        ready.current = true;
        // Incidente abierto desde la URL (?incidente=): centrarlo al terminar de cargar.
        const sel = latest.current.incidents.find((i) => i.id === latest.current.selectedId);
        if (sel && sel.lat !== null && sel.lon !== null) {
          map.jumpTo({ center: [sel.lon, sel.lat], zoom: 14.5 });
        }
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

  // Al seleccionar un incidente (lista, alarma o mapa), llevarlo al centro de la vista.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready.current || !map || !selectedId) return;
    const inc = latest.current.incidents.find((i) => i.id === selectedId);
    if (!inc || inc.lat === null || inc.lon === null) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.easeTo({
      center: [inc.lon, inc.lat],
      zoom: Math.max(map.getZoom(), 14.5),
      duration: reduce ? 0 : 600,
    });
  }, [selectedId]);

  useEffect(() => {
    if (!ready.current || !mapRef.current) return;
    if (barrios) mapRef.current.getSource<GeoJSONSource>("barrios")?.setData(barrios);
    if (manzanas) mapRef.current.getSource<GeoJSONSource>("manzanas")?.setData(manzanas);
  }, [barrios, manzanas]);

  return (
    <div className="relative h-full min-h-[420px] w-full">
      <div ref={container} className="h-full w-full" />
      {leyenda && <Leyenda incidents={incidents} basemap={basemap} />}
    </div>
  );
}

/** Leyenda viva: niveles de triaje y solo las categorías que hay en el mapa ahora. */
function Leyenda({ incidents, basemap }: { incidents: IncidentSummary[]; basemap: Basemap }) {
  const present = useMemo(() => {
    const count = new Map<Category, number>();
    for (const i of incidents) count.set(i.category, (count.get(i.category) ?? 0) + 1);
    return Array.from(count.entries()).sort((a, b) => b[1] - a[1]);
  }, [incidents]);

  return (
    <details
      open
      className="absolute bottom-8 left-2 max-h-[55%] w-[22rem] max-w-[calc(100%-1rem)] overflow-y-auto rounded-md border border-linea bg-white/95 text-xs shadow-[0_1px_0_#e4dcdb] backdrop-blur"
    >
      <summary className="cursor-pointer px-3 py-2 font-display text-sm font-semibold">
        Leyenda del mapa
      </summary>
      <div className="flex flex-col gap-3 px-3 pb-3">
        <ul className="grid grid-cols-4 gap-x-2 gap-y-1">
          {TRIAGE_ORDER.map((level) => (
            <li key={level} className="flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-3 rounded-full"
                style={{ background: TRIAGE_COLOR[level] }}
              />
              {TRIAGE_LABEL[level]}
            </li>
          ))}
        </ul>
        {present.length > 0 && (
          <ul className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-linea pt-2">
            {present.map(([cat, n]) => (
              <li key={cat} className="flex items-center gap-2">
                <IconoCategoria category={cat} size={18} className="text-tinta" />
                <span className="flex-1 leading-tight">{CATEGORY_LABEL[cat]}</span>
                <span className="tabular-nums text-tinta-suave">{n}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="border-t border-linea pt-2 leading-snug text-tinta-suave">
          Tamaño = número de reportes. Borde punteado = posible falso (sigue visible hasta que
          alguien lo revise).
        </p>
        <p className="leading-snug text-tinta-suave">
          {basemap === "osm" && "Mapa base: OpenStreetMap vía OpenFreeMap (en línea)."}
          {basemap === "offline" && "Sin internet: mapa base offline con barrios SIMULADOS."}
          {basemap === "cargando" && "Cargando mapa base…"}
        </p>
      </div>
    </details>
  );
}
