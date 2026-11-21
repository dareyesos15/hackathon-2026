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
  { color: "#f9d5c6", texto: "Pocos reportes" },
  { color: "#ee6a2c", texto: "Varios reportes" },
  { color: "#a3121f", texto: "Alta concentración" },
  { color: "#cfc6c4", texto: "Menos de 5 reportes (dato protegido)" },
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
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-2 text-white">
        <h1 className="font-display text-2xl font-semibold leading-none">Dacora</h1>
        <span className="text-sm text-white/75">Mapa público de afectación</span>
        <EtiquetaSimulado sobreOscuro />
        <span className="text-xs text-white/70">
          Se actualiza cada 10 s
          {manzanas?.cutoff_at ? ` · corte ${formatDateTime(manzanas.cutoff_at)}` : ""}
        </span>
        <nav className="ml-auto flex gap-3 text-sm">
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

      <main className="grid flex-1 grid-cols-1 gap-3 overflow-hidden p-4 lg:grid-cols-[1fr_300px]">
        <div className="min-h-[420px] overflow-hidden rounded-md border border-linea bg-white">
          <Mapa
            incidents={NO_INCIDENTS}
            barrios={barrios}
            manzanas={manzanas}
            selectedId={null}
            onSelect={noop}
            leyenda={false}
          />
        </div>
        <aside className="flex flex-col gap-4 overflow-y-auto rounded-xl bg-white p-4 text-sm">
          <section>
            <h2 className="mb-2 font-semibold">Reportes por manzana</h2>
            <ul className="flex flex-col gap-1.5">
              {LEYENDA.map((l) => (
                <li key={l.color} className="flex items-center gap-2">
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
              <p className="text-xl font-bold tabular-nums">{features.length}</p>
            </div>
            <div className="rounded-lg bg-papel p-2">
              <p className="text-xs text-tinta-suave">Barrios con reportes</p>
              <p className="text-xl font-bold tabular-nums">{barriosAfectados}</p>
            </div>
            <p className="col-span-2 text-xs text-tinta-suave">
              {visibles} manzanas con conteo publicable (k ≥ 5). Fuente: api · Dacora.
            </p>
          </section>
          <p className="text-xs text-tinta-suave">
            Este mapa muestra solo datos agregados: nunca nombres, teléfonos, direcciones exactas ni
            reportes individuales (Ley 1581 de 2012). Para reportar una emergencia, use el canal
            ciudadano o llame al 123. Geografía y datos SIMULADOS.
          </p>
        </aside>
      </main>
    </div>
  );
}
