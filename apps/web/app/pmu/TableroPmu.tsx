"use client";
/** Tablero situacional del PMU (US2). Solo en el navegador: usa sessionStorage, SSE y MapLibre. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Cifra } from "@/components/Cifra";
import { DetalleIncidente } from "@/components/DetalleIncidente";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { Mapa } from "@/components/Mapa";
import { MatrizTriaje } from "@/components/MatrizTriaje";
import { api } from "@/lib/api/client";
import { useLiveIncidents } from "@/lib/live";
import { clearSession, getSession } from "@/lib/session";
import { kpiMap, useKpi } from "@/lib/useKpi";

type FC = GeoJSON.FeatureCollection;

const MODE_LABEL = {
  conectando: { text: "Conectando…", cls: "bg-slate-200 text-slate-700" },
  en_vivo: { text: "En vivo", cls: "bg-emerald-100 text-emerald-800" },
  respaldo: { text: "Modo de respaldo (consulta cada 3 s)", cls: "bg-amber-100 text-amber-900" },
} as const;

function initialSelection(): string | null {
  return new URLSearchParams(window.location.search).get("incidente");
}

export default function TableroPmu() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [selectedId, setSelectedId] = useState<string | null>(initialSelection);
  const [barrios, setBarrios] = useState<FC | null>(null);
  const [manzanas, setManzanas] = useState<FC | null>(null);
  const token = session?.role === "operador_pmu" ? session.token : null;
  const live = useLiveIncidents(token);
  const kpis = kpiMap(useKpi(live.kpiRevision + Math.floor(live.revision / 10)));
  const incidents = useMemo(() => Array.from(live.incidents.values()), [live.incidents]);

  useEffect(() => {
    if (!token) router.replace("/");
  }, [token, router]);

  useEffect(() => {
    api.GET("/api/v1/geo/barrios").then(({ data }) => {
      if (data) setBarrios(data as unknown as FC);
    });
  }, []);

  // Capa por manzana: como máximo una consulta cada 5 s mientras llegan reportes.
  useEffect(() => {
    const timer = setTimeout(() => {
      api.GET("/api/v1/map/manzanas").then(({ data }) => {
        if (data) setManzanas(data as unknown as FC);
      });
    }, 1500);
    return () => clearTimeout(timer);
  }, [live.revision]);

  function select(id: string | null) {
    setSelectedId(id);
    const url = id ? `?incidente=${id}` : window.location.pathname;
    window.history.replaceState(null, "", url);
  }

  if (!token) return null;

  const critical = incidents.filter(
    (i) => i.is_life_threat && ["abierto", "en_revision"].includes(i.status),
  ).length;
  const received = kpis.reports_received;
  const consolidated = kpis.incidents_consolidated;
  const mode = MODE_LABEL[live.mode];

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="text-lg font-bold">Dacora · Tablero PMU</h1>
        <EtiquetaSimulado />
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${mode.cls}`}>{mode.text}</span>
        <nav className="ml-auto flex gap-3 text-sm">
          <Link href="/pmu/kpi/" className="text-slate-700 underline">
            Panel de KPI
          </Link>
          <button
            type="button"
            className="text-slate-500"
            onClick={() => {
              clearSession();
              router.replace("/");
            }}
          >
            Salir
          </button>
        </nav>
      </header>

      <section className="grid grid-cols-2 gap-2 px-4 py-2 md:grid-cols-4">
        {received && (
          <Cifra
            etiqueta="Reportes recibidos"
            valor={received.value ?? null}
            unidad="conteo"
            fuente={received.source}
            version={received.version}
            corte={received.cutoff_at}
            simulado
          />
        )}
        {consolidated && (
          <Cifra
            etiqueta="Incidentes consolidados"
            valor={consolidated.value ?? null}
            unidad="conteo"
            fuente={consolidated.source}
            version={consolidated.version}
            corte={consolidated.cutoff_at}
            simulado
          />
        )}
        <Cifra
          etiqueta="Riesgo vital pendiente de revisión"
          valor={critical}
          unidad="conteo"
          fuente="api · tablero"
          version={live.revision}
          corte={live.cutoffAt ?? new Date(0).toISOString()}
          estado={critical > 0 ? "alerta" : "ok"}
          simulado
        />
        {kpis.duplicate_detection_rate && (
          <Cifra
            etiqueta="Duplicados detectados"
            valor={kpis.duplicate_detection_rate.value ?? null}
            unidad="%"
            fuente={kpis.duplicate_detection_rate.source}
            version={kpis.duplicate_detection_rate.version}
            corte={kpis.duplicate_detection_rate.cutoff_at}
            meta="> 90 %"
            estado={(kpis.duplicate_detection_rate.value ?? 0) > 90 ? "ok" : "alerta"}
            simulado
          />
        )}
      </section>

      <main className="grid flex-1 grid-cols-1 gap-3 overflow-hidden px-4 pb-4 lg:grid-cols-[1fr_420px]">
        <div className="min-h-[420px] overflow-hidden rounded-xl bg-white shadow-sm">
          <Mapa
            incidents={incidents}
            barrios={barrios}
            manzanas={manzanas}
            selectedId={selectedId}
            onSelect={select}
          />
        </div>
        <aside className="overflow-hidden">
          {selectedId ? (
            <DetalleIncidente
              key={selectedId}
              incidentId={selectedId}
              incidents={incidents}
              revision={live.revision}
              onClose={() => select(null)}
              onSelect={select}
            />
          ) : (
            <MatrizTriaje incidents={incidents} selectedId={selectedId} onSelect={select} />
          )}
        </aside>
      </main>
    </div>
  );
}
