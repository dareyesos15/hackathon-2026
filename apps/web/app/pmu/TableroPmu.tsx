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
  conectando: { text: "Conectando…", cls: "bg-white/10 text-white/80" },
  en_vivo: { text: "En vivo", cls: "bg-white text-sangre" },
  respaldo: { text: "Modo de respaldo (consulta cada 3 s)", cls: "bg-[#ffd27a] text-tinta" },
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

  const pendingLife = incidents
    .filter((i) => i.is_life_threat && ["abierto", "en_revision"].includes(i.status))
    .sort((a, b) => a.first_seen.localeCompare(b.first_seen));
  const critical = pendingLife.length;
  const received = kpis.reports_received;
  const consolidated = kpis.incidents_consolidated;
  const mode = MODE_LABEL[live.mode];

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-stretch bg-sangre text-white">
        <div className="flex items-center gap-3 px-4 py-2">
          <h1 className="font-display text-2xl font-semibold leading-none">Dacora</h1>
          <span className="text-sm text-white/75">Tablero del PMU</span>
          <EtiquetaSimulado sobreOscuro />
          <span className={`rounded-sm px-2 py-0.5 text-xs font-bold ${mode.cls}`}>
            {live.mode === "en_vivo" && (
              <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-senal motion-reduce:animate-none" />
            )}
            {mode.text}
          </span>
        </div>
        {critical > 0 && (
          <button
            type="button"
            onClick={() => select(pendingLife[0].id)}
            className="flex items-center gap-2 bg-senal px-4 py-2 text-left font-bold hover:bg-[#b51723]"
          >
            <span className="font-display text-2xl leading-none tabular-nums">{critical}</span>
            <span className="text-sm leading-tight">
              con riesgo vital sin revisar
              <span className="block text-xs font-normal text-white/85">Abrir el más antiguo</span>
            </span>
          </button>
        )}
        <nav className="ml-auto flex items-center gap-4 px-4 text-sm">
          <Link href="/pmu/kpi/" className="underline decoration-white/40 underline-offset-4">
            Panel de KPI
          </Link>
          <button
            type="button"
            className="text-white/75 hover:text-white"
            onClick={() => {
              clearSession();
              router.replace("/");
            }}
          >
            Salir
          </button>
        </nav>
      </header>

      <section className="grid grid-cols-2 gap-2 px-4 py-3 md:grid-cols-4">
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
        <div className="min-h-[420px] overflow-hidden rounded-md border border-linea bg-white">
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
