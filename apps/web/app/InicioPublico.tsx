"use client";
/**
 * Tablero público de Dacora para todos, sin iniciar sesión (Ley 1712 de 2014): mapa con
 * pestañas de Triaje (incidentes por nivel y conteos por manzana con k ≥ 5), Cascada (riesgo por
 * manzana) y Zonas (zonas inseguras vigiladas), KPI con fuente y fecha de corte, alertas
 * oficiales del COE y el botón para reportar una emergencia (la ciudadanía no tiene cuenta).
 * Nunca reportes individuales, textos, recursos ni datos personales (Ley 1581 de 2012): los
 * incidentes llegan sin texto y con la ubicación redondeada a ~100 m.
 * La API se consulta siempre como anónima, con o sin sesión: todos ven lo mismo.
 */
import { DEMO_MODE } from "@/lib/env";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import Link from "next/link";
import { useMemo, useState } from "react";
import { AvisoAlerta, alertsFromGeoJSON } from "@/components/AvisoAlerta";
import {
  CapaCascada,
  selectionFrom,
  type CascadeLayer,
  type CascadeSelection,
} from "@/components/CapaCascada";
import { CifraKpi } from "@/components/CifraKpi";
import { Mapa } from "@/components/Mapa";
import { MatrizTriaje } from "@/components/MatrizTriaje";
import { ZonasPublicas } from "@/components/ZonasPublicas";
import { publicApi as api } from "@/lib/api/client";
import { useOfflineData } from "@/lib/offline";
import { formatDateTime, formatInt } from "@/lib/format";
import type { IncidentSummary } from "@/lib/labels";
import { AREA_HOME, ROLE_LABELS, clearSession, getSession } from "@/lib/session";
import { kpiMap, type Kpi } from "@/lib/useKpi";
import { zonesToGeoJSON, type ZoneSensorOut } from "@/lib/zones";

type FC = GeoJSON.FeatureCollection & { cutoff_at?: string };

const MAP_MS = 10000;
// La predicción de cascada se recalcula con lluvia o reportes nuevos; el público no tiene SSE.
const CASCADE_MS = 15000;
const KPI_MS = 5000;
// Alertas oficiales vigentes: < 5 s desde su emisión (specs/002 SC-006).
const ALERTS_MS = 4000;
const INCIDENTS_MS = 8000;
const ZONES_MS = 8000;
const NO_INCIDENTS: IncidentSummary[] = [];
const NO_ZONES: ZoneSensorOut[] = [];

type Tab = "triaje" | "cascada" | "zonas";
const TAB_LABEL: Record<Tab, string> = { triaje: "Triaje", cascada: "Cascada", zonas: "Zonas" };

const LEYENDA = [
  { color: "#f9d5c6", texto: "Pocos reportes" },
  { color: "#ee6a2c", texto: "Varios reportes" },
  { color: "#a3121f", texto: "Alta concentración" },
  { color: "#cfc6c4", texto: "Menos de 5 reportes (dato protegido)" },
  { color: "#f59e0b", texto: "Área de alerta oficial vigente" },
];

async function getData<T>(promise: Promise<{ data?: unknown }>): Promise<T | undefined> {
  return (await promise).data as T | undefined;
}

const DETECTION = ["duplicate_detection_rate", "critical_recall", "critical_auto_discarded"];
const OPERATION = [
  "critical_without_dispatch",
  "median_time_to_dispatch_min",
  "double_dispatch_prevented",
  "p95_processing_ms",
];

export default function InicioPublico() {
  const [session, setSession] = useState(getSession);
  const [tab, setTab] = useState<Tab>("triaje");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoneSel, setZoneSel] = useState<string | null>(null);
  const [cascadeOn, setCascadeOn] = useState(true);
  const [cascadeSel, setCascadeSel] = useState<CascadeSelection | null>(null);
  // Todo se guarda en el dispositivo: sin conexión se ve la última información recibida.
  const barrios = useOfflineData<FC>("barrios", () => getData(api.GET("/api/v1/geo/barrios"))).data;
  const manzanasData = useOfflineData<FC>(
    "manzanas-publico",
    () => getData(api.GET("/api/v1/map/manzanas")),
    { pollMs: MAP_MS },
  );
  const alertsData = useOfflineData<FC>(
    "alertas-vigentes",
    () => getData(api.GET("/api/v1/alerts/active")),
    { pollMs: ALERTS_MS },
  );
  const kpiData = useOfflineData<Kpi[]>(
    "kpi",
    async () => (await api.GET("/api/v1/metrics/kpi")).data?.items,
    { pollMs: KPI_MS },
  );
  const cascadeData = useOfflineData<CascadeLayer>(
    "cascade-publico",
    () => getData(api.GET("/api/v1/map/cascade")),
    { enabled: tab === "cascada" && cascadeOn, pollMs: CASCADE_MS },
  );
  const incidentsData = useOfflineData<IncidentSummary[]>(
    "incidentes-publico",
    async () => (await api.GET("/api/v1/incidents")).data?.items,
    { enabled: tab === "triaje", pollMs: INCIDENTS_MS },
  );
  const zonesData = useOfflineData<ZoneSensorOut[]>(
    "zonas-publico",
    async () => (await api.GET("/api/v1/sensors/zones")).data?.items,
    { enabled: tab === "zonas", pollMs: ZONES_MS },
  );
  const incidents = incidentsData.data ?? NO_INCIDENTS;
  const zoneSensors = zonesData.data ?? NO_ZONES;
  const zonesFc = useMemo(() => zonesToGeoJSON(zoneSensors), [zoneSensors]);
  const manzanas = manzanasData.data;
  const alerts = alertsData.data;
  const items = kpiData.data ?? [];
  const k = kpiMap(items);
  const panel = session ? AREA_HOME[session.role] : "/";
  const offline =
    manzanasData.offline || kpiData.offline || alertsData.offline || incidentsData.offline;

  const features = manzanas?.features ?? [];
  const visibles = features.filter((f) => f.properties?.report_count != null).length;
  const barriosAfectados = new Set(features.map((f) => f.properties?.barrio)).size;
  const received = k.reports_received;
  const consolidated = k.incidents_consolidated;
  const mapLatency = k.time_to_consolidated_map_min;
  const latestCut = items.reduce<string | null>(
    (acc, item) => (!acc || item.cutoff_at > acc ? item.cutoff_at : acc),
    null,
  );

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-2 text-white">
        <h1 className="font-display text-2xl font-semibold leading-none">Dacora</h1>
        <EtiquetaSimulado sobreOscuro />
        <span className="hidden text-sm text-white/75 sm:inline">
          Manizales · mapa, predicción e indicadores públicos
        </span>
        <nav className="ml-auto flex flex-wrap items-center gap-3 text-sm">
          <Link
            href="/reportar/"
            className="rounded-sm bg-senal px-3 py-1.5 font-bold text-white hover:bg-sangre-claro"
          >
            Reportar una emergencia
          </Link>
          {session ? (
            <>
              <span className="text-white/75">
                {session.displayName} · {ROLE_LABELS[session.role]}
              </span>
              <Link href={panel} className="underline decoration-white/40 underline-offset-4">
                Ir a mi panel
              </Link>
              <button
                type="button"
                className="text-white/75 hover:text-white"
                onClick={() => {
                  clearSession();
                  setSession(null);
                }}
              >
                Salir
              </button>
            </>
          ) : (
            <Link
              href="/ingresar/"
              className="text-white/85 underline decoration-white/40 underline-offset-4"
            >
              Entidades: iniciar sesión
            </Link>
          )}
        </nav>
      </header>

      {offline && (
        <p className="mx-4 mt-3 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
          Sin conexión: se muestra la última información recibida
          {manzanasData.savedAt ? ` (${formatDateTime(manzanasData.savedAt)})` : ""}. Se actualiza
          sola al volver la conexión.
        </p>
      )}

      <div className="px-4 pt-3">
        <AvisoAlerta alerts={alertsFromGeoJSON(alerts)} />
      </div>

      <section className="mx-4 mt-3 grid gap-4 rounded-md bg-sangre p-5 text-white md:grid-cols-2">
        <div>
          <p className="text-sm text-white/75">Información dispersa → decisiones consolidadas</p>
          <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums sm:text-5xl">
            {received?.value != null ? formatInt(received.value) : "—"} reportes →{" "}
            {consolidated?.value != null ? formatInt(consolidated.value) : "—"} incidentes
          </p>
          {DEMO_MODE && (
            <p className="mt-1 text-xs text-white/70">
              Fuente: api · corte {received ? formatDateTime(received.cutoff_at) : "—"}
            </p>
          )}
        </div>
        <div>
          <p className="text-sm text-white/75">Cada hecho aparece en el mapa (p90)</p>
          <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums sm:text-5xl">
            {mapLatency?.value != null
              ? `${mapLatency.value.toLocaleString("es-CO", { maximumFractionDigits: 1 })} min`
              : "—"}
          </p>
          <p className="mt-1 text-xs text-white/70">
            Tiempo desde que llega un hecho hasta que aparece consolidado en el mapa.
            {DEMO_MODE && ` Fuente: ${mapLatency?.source ?? "api"}.`}
          </p>
        </div>
      </section>

      <main className="grid gap-3 p-4 lg:grid-cols-[1fr_360px]">
        <div className="h-[60vh] min-h-[420px] overflow-hidden rounded-md border border-linea bg-white">
          <Mapa
            incidents={tab === "triaje" ? incidents : NO_INCIDENTS}
            barrios={barrios}
            manzanas={tab === "triaje" ? manzanas : null}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
            alertAreas={alerts}
            leyenda={tab === "triaje"}
            cascade={tab === "cascada" && cascadeOn ? cascadeData.data : null}
            onCascadeSelect={(props) => setCascadeSel(selectionFrom(props, cascadeData.data))}
            zones={tab === "zonas" ? zonesFc : null}
            onZoneSelect={setZoneSel}
          />
        </div>
        <aside className="flex max-h-[80vh] flex-col gap-3 overflow-hidden rounded-md border border-linea bg-white p-4 text-sm">
          <nav className="flex gap-1" aria-label="Módulos del tablero">
            {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                aria-pressed={tab === t}
                className={`flex-1 rounded px-2 py-1 text-sm font-medium ${
                  tab === t ? "bg-slate-900 text-white" : "bg-papel text-slate-700"
                }`}
              >
                {TAB_LABEL[t]}
              </button>
            ))}
          </nav>
          <div className="flex-1 overflow-y-auto">
            {tab === "triaje" && (
              <div className="flex flex-col gap-4">
                <MatrizTriaje
                  incidents={incidents}
                  selectedId={selectedId}
                  onSelect={(id) => setSelectedId(id === selectedId ? null : id)}
                />
                <section>
                  <h2 className="mb-2 font-semibold">Reportes por manzana</h2>
                  <ul className="flex flex-col gap-1.5">
                    {LEYENDA.map((l) => (
                      <li key={l.texto} className="flex items-center gap-2">
                        <span
                          className="inline-block h-3 w-5 rounded-sm border border-linea"
                          style={{ backgroundColor: l.color }}
                        />
                        {l.texto}
                      </li>
                    ))}
                  </ul>
                </section>
                <section className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-papel p-2">
                    <p className="text-xs text-tinta-suave">Manzanas con reportes</p>
                    <p className="text-xl font-bold tabular-nums">{formatInt(features.length)}</p>
                  </div>
                  <div className="rounded-lg bg-papel p-2">
                    <p className="text-xs text-tinta-suave">Barrios con reportes</p>
                    <p className="text-xl font-bold tabular-nums">{formatInt(barriosAfectados)}</p>
                  </div>
                  <p className="col-span-2 text-xs text-tinta-suave">
                    {formatInt(visibles)} manzanas con conteo publicable (k ≥ 5).
                    {DEMO_MODE &&
                      ` Fuente: api · corte ${manzanas?.cutoff_at ? formatDateTime(manzanas.cutoff_at) : "—"}.`}
                  </p>
                </section>
              </div>
            )}
            {tab === "cascada" && (
              <CapaCascada
                enabled={cascadeOn}
                onToggle={(on) => {
                  setCascadeOn(on);
                  if (!on) setCascadeSel(null);
                }}
                layer={cascadeData.data}
                selected={cascadeSel}
                canControlRain={false}
                offline={cascadeData.offline}
                savedAt={cascadeData.savedAt}
              />
            )}
            {tab === "zonas" && (
              <ZonasPublicas sensors={zoneSensors} selectedId={zoneSel} onSelect={setZoneSel} />
            )}
          </div>
          <p className="text-xs text-tinta-suave">
            Sin datos personales: nunca nombres, teléfonos, textos de reportes ni direcciones
            exactas (ubicación aproximada a ~100 m). Para reportar una emergencia use{" "}
            <Link href="/reportar/" className="underline underline-offset-2">
              Reportar
            </Link>{" "}
            o llame al 123.
          </p>
        </aside>
      </main>

      <section className="px-4">
        <h2 className="mb-2 font-display text-xl font-semibold">
          Detección de duplicados y seguridad de los críticos
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {DETECTION.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
        {!k.duplicate_detection_rate && (
          <p className="mt-2 text-sm text-tinta-suave">Aún no hay datos de evaluación.</p>
        )}
      </section>

      <section className="px-4 pt-4">
        <h2 className="mb-2 font-display text-xl font-semibold">Respuesta y operación</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {OPERATION.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
      </section>

      <footer className="px-4 py-4 text-xs text-tinta-suave">
        Se actualiza sola
        {DEMO_MODE && latestCut ? ` · último corte ${formatDateTime(latestCut)}` : ""}.
      </footer>
    </div>
  );
}
