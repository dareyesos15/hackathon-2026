"use client";
/**
 * Panel de KPI medido en vivo (US3, FR-028/FR-029): cada cifra con fuente, versión y corte.
 * Los KPI de detección los publica scripts/evaluate_kpis.py contra la verdad del escenario
 * SIMULADO; la API no la conoce (principio IV).
 */
import { DEMO_MODE } from "@/lib/env";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CifraKpi } from "@/components/CifraKpi";
import { formatDateTime, formatInt } from "@/lib/format";
import { getSession } from "@/lib/session";
import { kpiMap, useKpi } from "@/lib/useKpi";

const REFRESH_MS = 5000;

export default function PanelKpi() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [tick, setTick] = useState(0);
  const items = useKpi(tick);
  const k = kpiMap(items);
  const allowed = true; // KPI agregados: visibles para todos, con o sin sesión

  useEffect(() => {
    if (!allowed) {
      router.replace("/ingresar/");
      return;
    }
    const timer = setInterval(() => setTick((t) => t + 1), REFRESH_MS);
    return () => clearInterval(timer);
  }, [allowed, router]);

  if (!allowed) return null;

  const detection = ["duplicate_detection_rate", "critical_recall", "critical_auto_discarded"];
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
        <h1 className="font-display text-3xl font-semibold">Panel de KPI de Dacora</h1>
        <EtiquetaSimulado />
        <span className="text-xs text-tinta-suave">
          Se actualiza cada 5 s
          {DEMO_MODE && latestCut ? ` · último corte ${formatDateTime(latestCut)}` : ""}
        </span>
        {session?.role === "pmu" && (
          <Link href="/pmu/" className="ml-auto text-sm underline">
            Volver al tablero
          </Link>
        )}
        {session?.role !== "pmu" && (
          <Link href="/" className="ml-auto text-sm underline">
            Ver mapa e indicadores
          </Link>
        )}
      </header>

      <section className="grid gap-4 rounded-md bg-sangre p-5 text-white md:grid-cols-2">
        <div>
          <p className="text-sm text-white/75">Información dispersa → decisiones consolidadas</p>
          <p className="mt-1 font-display text-5xl font-semibold leading-none tabular-nums">
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
          <p className="mt-1 font-display text-5xl font-semibold leading-none tabular-nums">
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

      <section>
        <h2 className="mb-2 font-display text-xl font-semibold">
          Detección de duplicados y seguridad de los críticos
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {detection.map((key) => (k[key] ? <CifraKpi key={key} k={k[key]} /> : null))}
        </div>
        {!k.duplicate_detection_rate && (
          <p className="mt-2 text-sm text-tinta-suave">Aún no hay datos de evaluación.</p>
        )}
      </section>

      <section>
        <h2 className="mb-2 font-display text-xl font-semibold">Operación del motor</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {["reports_received", "incidents_consolidated", "p95_processing_ms"].map((key) =>
            k[key] ? <CifraKpi key={key} k={k[key]} /> : null,
          )}
        </div>
      </section>
    </main>
  );
}
