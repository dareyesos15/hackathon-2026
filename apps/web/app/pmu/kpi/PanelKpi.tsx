"use client";
/**
 * Panel de KPI medido en vivo (US3, FR-028/FR-029): cada cifra con fuente, versión y corte.
 * Los KPI de detección los publica scripts/evaluate_kpis.py contra la verdad del escenario
 * SIMULADO; la API no la conoce (principio IV).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Cifra, type CifraProps } from "@/components/Cifra";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { formatDateTime, formatInt } from "@/lib/format";
import { getSession } from "@/lib/session";
import { kpiMap, useKpi, type Kpi } from "@/lib/useKpi";

const REFRESH_MS = 5000;

type Estado = CifraProps["estado"];

function estado(k: Kpi): Estado {
  const v = k.value;
  if (v === null || v === undefined) return "neutral";
  switch (k.indicator) {
    case "duplicate_detection_rate":
    case "fake_detection_rate":
      return v > 90 ? "ok" : "alerta";
    case "critical_recall":
      return v >= 98 ? "ok" : "alerta";
    case "critical_auto_discarded":
      return v === 0 ? "ok" : "alerta";
    case "p95_processing_ms":
      return v < 1000 ? "ok" : "alerta";
    default:
      return "neutral";
  }
}

function CifraKpi({ k }: { k: Kpi }) {
  return (
    <Cifra
      etiqueta={k.label}
      valor={k.value ?? null}
      unidad={k.unit}
      fuente={k.source}
      version={k.version}
      corte={k.cutoff_at}
      meta={k.target ?? undefined}
      estado={estado(k)}
      simulado={k.simulated}
    />
  );
}

export default function PanelKpi() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [tick, setTick] = useState(0);
  const items = useKpi(tick);
  const k = kpiMap(items);
  const allowed = session?.role === "operador_pmu" || session?.role === "publico";

  useEffect(() => {
    if (!allowed) {
      router.replace("/");
      return;
    }
    const timer = setInterval(() => setTick((t) => t + 1), REFRESH_MS);
    return () => clearInterval(timer);
  }, [allowed, router]);

  if (!allowed) return null;

  const detection = [
    "duplicate_detection_rate",
    "fake_detection_rate",
    "false_positive_rate",
    "critical_recall",
    "critical_auto_discarded",
  ];
  const received = k.reports_received;
  const consolidated = k.incidents_consolidated;
  const mapLatency = k.time_to_consolidated_map_min;
  const latestCut = items.reduce<string | null>(
    (acc, item) => (!acc || item.cutoff_at > acc ? item.cutoff_at : acc),
    null,
  );

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">Dacora · Panel de KPI</h1>
        <EtiquetaSimulado />
        <span className="text-xs text-slate-500">
          Se actualiza cada 5 s{latestCut ? ` · último corte ${formatDateTime(latestCut)}` : ""}
        </span>
        {session?.role === "operador_pmu" && (
          <Link href="/pmu/" className="ml-auto text-sm underline">
            Volver al tablero
          </Link>
        )}
        {session?.role === "publico" && (
          <Link href="/mapa/" className="ml-auto text-sm underline">
            Ver mapa público
          </Link>
        )}
      </header>

      <section className="grid gap-4 rounded-xl bg-slate-900 p-5 text-white md:grid-cols-2">
        <div>
          <p className="text-sm text-slate-300">Información dispersa → decisiones consolidadas</p>
          <p className="mt-1 text-4xl font-bold tabular-nums">
            {received?.value != null ? formatInt(received.value) : "—"} reportes →{" "}
            {consolidated?.value != null ? formatInt(consolidated.value) : "—"} incidentes
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Fuente: api · corte {received ? formatDateTime(received.cutoff_at) : "—"}
          </p>
        </div>
        <div>
          <p className="text-sm text-slate-300">Cada hecho aparece en el mapa (p90)</p>
          <p className="mt-1 text-4xl font-bold tabular-nums">
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

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          Detección de duplicados y falsos (KPI oficial &gt; 90 %) y seguridad de los críticos
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {detection.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
        {!k.duplicate_detection_rate && (
          <p className="mt-2 text-sm text-slate-500">
            Aún no hay evaluación: ejecute la reproducción del escenario
            (scripts/replay_scenario.py).
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Operación del motor</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {["reports_received", "incidents_consolidated", "p95_processing_ms"].map((key) =>
            k[key] ? <CifraKpi key={key} k={k[key]} /> : null,
          )}
        </div>
      </section>

      <footer className="text-xs text-slate-500">
        Definiciones en docs/diccionario_indicadores.md. Los porcentajes de detección se calculan
        contra la verdad del escenario sintético, que el motor nunca ve. Datos SIMULADOS.
      </footer>
    </main>
  );
}
