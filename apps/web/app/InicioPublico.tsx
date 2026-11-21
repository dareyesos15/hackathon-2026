"use client";
/**
 * Inicio público de Dacora: mapa de afectación e indicadores para todos, sin iniciar sesión
 * (Ley 1712 de 2014). Solo agregados: conteos por manzana con k ≥ 5 (los aplica la API), KPI
 * con fuente y fecha de corte, y alertas oficiales emitidas por el COE. Nunca incidentes,
 * reportes individuales, recursos ni datos personales (Ley 1581 de 2012).
 * La API se consulta siempre con el rol `publico`, también con sesión de Ciudadanía o
 * Administrador: todos ven el mismo mapa agregado.
 */
import Link from "next/link";
import { useState } from "react";
import { AvisoAlerta, alertsFromGeoJSON } from "@/components/AvisoAlerta";
import {
  CapaCascada,
  selectionFrom,
  type CascadeLayer,
  type CascadeSelection,
} from "@/components/CapaCascada";
import { CifraKpi } from "@/components/CifraKpi";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { Mapa } from "@/components/Mapa";
import { publicApi as api } from "@/lib/api/client";
import { useOfflineData } from "@/lib/offline";
import { formatDateTime, formatInt } from "@/lib/format";
import { ROLE_LABELS, clearSession, getSession, type Role } from "@/lib/session";
import { kpiMap, type Kpi } from "@/lib/useKpi";

type FC = GeoJSON.FeatureCollection & { cutoff_at?: string };

const MAP_MS = 10000;
// La predicción de cascada se recalcula con lluvia o reportes nuevos; el público no tiene SSE.
const CASCADE_MS = 15000;
const KPI_MS = 5000;
// Alertas oficiales vigentes: < 5 s desde su emisión (specs/002 SC-006).
const ALERTS_MS = 4000;
const NO_INCIDENTS: never[] = [];
const noop = () => {};

const PANEL: Record<Role, string> = {
  ciudadano: "/reportar/",
  pmu: "/pmu/",
  admin: "/admin/",
};

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
  const [cascadeOn, setCascadeOn] = useState(false);
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
    { enabled: cascadeOn, pollMs: CASCADE_MS },
  );
  const manzanas = manzanasData.data;
  const alerts = alertsData.data;
  const items = kpiData.data ?? [];
  const k = kpiMap(items);
  const panel = session ? PANEL[session.role] : "/";
  const offline = manzanasData.offline || kpiData.offline || alertsData.offline;

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
        <nav className="ml-auto flex items-center gap-3 text-sm">
          {session ? (
            <>
              <span className="text-white/75">{ROLE_LABELS[session.role]}</span>
              {session.role === "ciudadano" ? (
                <Link
                  href={panel}
                  className="rounded-sm bg-senal px-3 py-1.5 font-bold text-white hover:bg-sangre-claro"
                >
                  Reportar una emergencia
                </Link>
              ) : (
                <Link
                  href={panel}
                  className="rounded-sm bg-senal px-3 py-1.5 font-bold text-white hover:bg-sangre-claro"
                >
                  Ir a mi panel
                </Link>
              )}
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
              className="rounded-sm bg-senal px-3 py-1.5 font-bold text-white hover:bg-sangre-claro"
            >
              Iniciar sesión
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
          <p className="mt-1 text-xs text-white/70">
            Fuente: api · corte {received ? formatDateTime(received.cutoff_at) : "—"}
          </p>
        </div>
        <div>
          <p className="text-sm text-white/75">Cada hecho aparece en el mapa (p90)</p>
          <p className="mt-1 font-display text-4xl font-semibold leading-none tabular-nums sm:text-5xl">
            {mapLatency?.value != null
              ? `${mapLatency.value.toLocaleString("es-CO", { maximumFractionDigits: 1 })} min`
              : "—"}
          </p>
          <p className="mt-1 text-xs text-white/70">
            Tiempo desde que llega un hecho hasta que aparece consolidado en el mapa. Fuente:{" "}
            {mapLatency?.source ?? "evaluate_kpis.py"}.
          </p>
        </div>
      </section>

      <main className="grid gap-3 p-4 lg:grid-cols-[1fr_300px]">
        <div className="h-[60vh] min-h-[420px] overflow-hidden rounded-md border border-linea bg-white">
          <Mapa
            incidents={NO_INCIDENTS}
            barrios={barrios}
            manzanas={manzanas}
            selectedId={null}
            onSelect={noop}
            alertAreas={alerts}
            leyenda={false}
            cascade={cascadeOn ? cascadeData.data : null}
            onCascadeSelect={(props) => setCascadeSel(selectionFrom(props, cascadeData.data))}
          />
        </div>
        <aside className="flex flex-col gap-4 rounded-md border border-linea bg-white p-4 text-sm">
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
          <section>
            <h2 className="mb-2 font-semibold">Reportes por manzana</h2>
            {cascadeOn && (
              <p className="mb-1 text-xs text-tinta-suave">
                Con la predicción activa, el color de las manzanas muestra el riesgo de cascada.
              </p>
            )}
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
              {formatInt(visibles)} manzanas con conteo publicable (k ≥ 5). Fuente: api · corte{" "}
              {manzanas?.cutoff_at ? formatDateTime(manzanas.cutoff_at) : "—"}.
            </p>
          </section>
          <p className="text-xs text-tinta-suave">
            Solo datos agregados: nunca nombres, teléfonos, direcciones exactas ni reportes
            individuales (Ley 1581 de 2012). Para reportar una emergencia, inicie sesión como
            ciudadanía o llame al 123.
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
          <p className="mt-2 text-sm text-tinta-suave">
            Aún no hay evaluación: el escenario aún no se ha reproducido.
          </p>
        )}
      </section>

      <section className="px-4 pt-4">
        <h2 className="mb-2 font-display text-xl font-semibold">Respuesta y operación</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {OPERATION.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
      </section>

      <footer className="px-4 py-4 text-xs text-tinta-suave">
        Se actualiza sola{latestCut ? ` · último corte ${formatDateTime(latestCut)}` : ""}.
        Definiciones en docs/diccionario_indicadores.md. Los porcentajes de detección se calculan
        contra la verdad del escenario sintético, que el motor nunca ve. Datos SIMULADOS. La IA solo
        sugiere; decide un humano.
      </footer>
    </div>
  );
}
