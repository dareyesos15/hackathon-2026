"use client";
/**
 * Mapa público de afectación (Ley 1712 de 2014 + Ley 1581 de 2012): solo agregados por
 * manzana con k-anonimato (k ≥ 5, lo aplica la API). Sin puntos de incidentes ni detalle
 * de reportes: esas ubicaciones exactas son solo para el PMU.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { Mapa } from "@/components/Mapa";
import { api } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { clearSession, getSession } from "@/lib/session";

type FC = GeoJSON.FeatureCollection & { cutoff_at?: string };

const REFRESH_MS = 10000;
const NO_INCIDENTS: never[] = [];
const noop = () => {};

const LEYENDA = [
  { color: "#fde68a", texto: "Pocos reportes" },
  { color: "#fb923c", texto: "Varios reportes" },
  { color: "#b91c1c", texto: "Alta concentración" },
  { color: "#cbd5e1", texto: "Menos de 5 reportes (dato protegido)" },
];

export default function MapaPublico() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [barrios, setBarrios] = useState<FC | null>(null);
  const [manzanas, setManzanas] = useState<FC | null>(null);
  const allowed = session?.role === "publico" || session?.role === "operador_pmu";

  useEffect(() => {
    if (!allowed) {
      router.replace("/");
      return;
    }
    api.GET("/api/v1/geo/barrios").then(({ data }) => {
      if (data) setBarrios(data as unknown as FC);
    });
    const load = () =>
      api.GET("/api/v1/map/manzanas").then(({ data }) => {
        if (data) setManzanas(data as unknown as FC);
      });
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [allowed, router]);

  if (!allowed) return null;

  const features = manzanas?.features ?? [];
  const visibles = features.filter((f) => f.properties?.report_count != null).length;
  const barriosAfectados = new Set(features.map((f) => f.properties?.barrio)).size;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="text-lg font-bold">Dacora · Mapa público de afectación</h1>
        <EtiquetaSimulado />
        <span className="text-xs text-slate-500">
          Se actualiza cada 10 s
          {manzanas?.cutoff_at ? ` · corte ${formatDateTime(manzanas.cutoff_at)}` : ""}
        </span>
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

      <main className="grid flex-1 grid-cols-1 gap-3 overflow-hidden p-4 lg:grid-cols-[1fr_300px]">
        <div className="min-h-[420px] overflow-hidden rounded-xl bg-white shadow-sm">
          <Mapa
            incidents={NO_INCIDENTS}
            barrios={barrios}
            manzanas={manzanas}
            selectedId={null}
            onSelect={noop}
          />
        </div>
        <aside className="flex flex-col gap-4 overflow-y-auto rounded-xl bg-white p-4 text-sm shadow-sm">
          <section>
            <h2 className="mb-2 font-semibold">Reportes por manzana</h2>
            <ul className="flex flex-col gap-1.5">
              {LEYENDA.map((l) => (
                <li key={l.color} className="flex items-center gap-2">
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
              <p className="text-xl font-bold tabular-nums">{features.length}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-2">
              <p className="text-xs text-slate-500">Barrios con reportes</p>
              <p className="text-xl font-bold tabular-nums">{barriosAfectados}</p>
            </div>
            <p className="col-span-2 text-xs text-slate-500">
              {visibles} manzanas con conteo publicable (k ≥ 5). Fuente: api · Dacora.
            </p>
          </section>
          <p className="text-xs text-slate-500">
            Este mapa muestra solo datos agregados: nunca nombres, teléfonos, direcciones exactas ni
            reportes individuales (Ley 1581 de 2012). Para reportar una emergencia, use el canal
            ciudadano o llame al 123. Geografía y datos SIMULADOS.
          </p>
        </aside>
      </main>
    </div>
  );
}
