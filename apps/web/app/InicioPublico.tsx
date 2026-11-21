"use client";
/**
 * Inicio público de Dacora: mapa de afectación e indicadores para todos, sin iniciar sesión
 * (Ley 1712 de 2014). Solo agregados: conteos por manzana con k ≥ 5 (los aplica la API), KPI
 * con fuente y fecha de corte, y alertas oficiales emitidas por el COE. Nunca incidentes,
 * reportes individuales, recursos ni datos personales (Ley 1581 de 2012).
 * Sin sesión, la API se consulta con el rol `publico`.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { AvisoAlerta, alertsFromGeoJSON } from "@/components/AvisoAlerta";
import { CifraKpi } from "@/components/CifraKpi";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { Mapa } from "@/components/Mapa";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt } from "@/lib/format";
import { ROLE_LABELS, clearSession, getSession, type Role } from "@/lib/session";
import { kpiMap, useKpi } from "@/lib/useKpi";

type FC = GeoJSON.FeatureCollection & { cutoff_at?: string };

const MAP_MS = 10000;
const KPI_MS = 5000;
// Alertas oficiales vigentes: < 5 s desde su emisión (specs/002 SC-006).
const ALERTS_MS = 4000;
const NO_INCIDENTS: never[] = [];
const noop = () => {};

const PANEL: Partial<Record<Role, string>> = {
  operador_pmu: "/pmu/",
  coe: "/pmu/",
  agencia: "/agencia/",
  ciudadano: "/reportar/",
};

const LEYENDA = [
  { color: "#fde68a", texto: "Pocos reportes" },
  { color: "#fb923c", texto: "Varios reportes" },
  { color: "#b91c1c", texto: "Alta concentración" },
  { color: "#cbd5e1", texto: "Menos de 5 reportes (dato protegido)" },
  { color: "#f59e0b", texto: "Área de alerta oficial vigente" },
];

const DETECTION = [
  "duplicate_detection_rate",
  "fake_detection_rate",
  "false_positive_rate",
  "critical_recall",
  "critical_auto_discarded",
];
const OPERATION = [
  "critical_without_dispatch",
  "median_time_to_dispatch_min",
  "double_dispatch_prevented",
  "p95_processing_ms",
];

export default function InicioPublico() {
  const [session, setSession] = useState(getSession);
  const [barrios, setBarrios] = useState<FC | null>(null);
  const [manzanas, setManzanas] = useState<FC | null>(null);
  const [alerts, setAlerts] = useState<FC | null>(null);
  const [tick, setTick] = useState(0);
  const items = useKpi(tick);
  const k = kpiMap(items);
  const panel = session ? PANEL[session.role] : undefined;

  useEffect(() => {
    api.GET("/api/v1/geo/barrios").then(({ data }) => {
      if (data) setBarrios(data as unknown as FC);
    });
    const loadMap = () =>
      api.GET("/api/v1/map/manzanas").then(({ data }) => {
        if (data) setManzanas(data as unknown as FC);
      });
    const loadAlerts = () =>
      api.GET("/api/v1/alerts/active").then(({ data }) => {
        if (data) setAlerts(data as unknown as FC);
      });
    void loadMap();
    void loadAlerts();
    const timers = [
      setInterval(() => void loadMap(), MAP_MS),
      setInterval(() => void loadAlerts(), ALERTS_MS),
      setInterval(() => setTick((t) => t + 1), KPI_MS),
    ];
    return () => timers.forEach(clearInterval);
  }, []);

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
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <h1 className="text-xl font-bold tracking-tight">Dacora</h1>
        <EtiquetaSimulado />
        <span className="hidden text-sm text-slate-600 sm:inline">
          Sismo del 10 ago 2026 · Manizales · mapa e indicadores públicos
        </span>
        <nav className="ml-auto flex items-center gap-3 text-sm">
          {session ? (
            <>
              <span className="text-slate-500">{ROLE_LABELS[session.role]}</span>
              {panel && (
                <Link
                  href={panel}
                  className="rounded-lg bg-slate-900 px-3 py-1.5 font-medium text-white"
                >
                  Ir a mi panel
                </Link>
              )}
              <button
                type="button"
                className="text-slate-500"
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
              className="rounded-lg bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700"
            >
              Iniciar sesión
            </Link>
          )}
        </nav>
      </header>

      <div className="px-4 pt-3">
        <AvisoAlerta alerts={alertsFromGeoJSON(alerts)} />
      </div>

      <section className="mx-4 mt-3 grid gap-4 rounded-xl bg-slate-900 p-5 text-white md:grid-cols-2">
        <div>
          <p className="text-sm text-slate-300">Información dispersa → decisiones consolidadas</p>
          <p className="mt-1 text-3xl font-bold tabular-nums sm:text-4xl">
            {received?.value != null ? formatInt(received.value) : "—"} reportes →{" "}
            {consolidated?.value != null ? formatInt(consolidated.value) : "—"} incidentes
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Fuente: api · corte {received ? formatDateTime(received.cutoff_at) : "—"}
          </p>
        </div>
        <div>
          <p className="text-sm text-slate-300">Cada hecho aparece en el mapa (p90)</p>
          <p className="mt-1 text-3xl font-bold tabular-nums sm:text-4xl">
            {mapLatency?.value != null
              ? `${mapLatency.value.toLocaleString("es-CO", { maximumFractionDigits: 1 })} min`
              : "—"}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            En el sismo real, las cifras de viviendas afectadas cambiaron durante días (1.449 →
            2.700 → 1.512, 13–15 ago). Fuente: {mapLatency?.source ?? "evaluate_kpis.py"}.
          </p>
        </div>
      </section>

      <main className="grid gap-3 p-4 lg:grid-cols-[1fr_300px]">
        <div className="h-[60vh] min-h-[420px] overflow-hidden rounded-xl bg-white shadow-sm">
          <Mapa
            incidents={NO_INCIDENTS}
            barrios={barrios}
            manzanas={manzanas}
            selectedId={null}
            onSelect={noop}
            alertAreas={alerts}
          />
        </div>
        <aside className="flex flex-col gap-4 rounded-xl bg-white p-4 text-sm shadow-sm">
          <section>
            <h2 className="mb-2 font-semibold">Reportes por manzana</h2>
            <ul className="flex flex-col gap-1.5">
              {LEYENDA.map((l) => (
                <li key={l.texto} className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-5 rounded-sm border border-slate-300"
                    style={{ backgroundColor: l.color }}
                  />
                  {l.texto}
                </li>
              ))}
            </ul>
          </section>
          <section className="grid grid-cols-2 gap-2">
            <div className="rounded-lg bg-slate-50 p-2">
              <p className="text-xs text-slate-500">Manzanas con reportes</p>
              <p className="text-xl font-bold tabular-nums">{formatInt(features.length)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-2">
              <p className="text-xs text-slate-500">Barrios con reportes</p>
              <p className="text-xl font-bold tabular-nums">{formatInt(barriosAfectados)}</p>
            </div>
            <p className="col-span-2 text-xs text-slate-500">
              {formatInt(visibles)} manzanas con conteo publicable (k ≥ 5). Fuente: api · corte{" "}
              {manzanas?.cutoff_at ? formatDateTime(manzanas.cutoff_at) : "—"}.
            </p>
          </section>
          <p className="text-xs text-slate-500">
            Solo datos agregados: nunca nombres, teléfonos, direcciones exactas ni reportes
            individuales (Ley 1581 de 2012). Para reportar una emergencia, inicie sesión como
            ciudadanía o llame al 123.
          </p>
        </aside>
      </main>

      <section className="px-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          Detección de duplicados y falsos (KPI oficial &gt; 90 %) y seguridad de los críticos
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {DETECTION.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
        {!k.duplicate_detection_rate && (
          <p className="mt-2 text-sm text-slate-500">
            Aún no hay evaluación: el escenario del sismo no se ha reproducido.
          </p>
        )}
      </section>

      <section className="px-4 pt-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Respuesta y operación</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {OPERATION.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
      </section>

      <footer className="px-4 py-4 text-xs text-slate-500">
        Se actualiza sola{latestCut ? ` · último corte ${formatDateTime(latestCut)}` : ""}.
        Definiciones en docs/diccionario_indicadores.md. Los porcentajes de detección se calculan
        contra la verdad del escenario sintético, que el motor nunca ve. Datos SIMULADOS. La IA solo
        sugiere; decide un humano.
      </footer>
    </div>
  );
}
