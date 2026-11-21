"use client";
/**
 * Recuperación post-sismo (specs/003, bloque 6 del diagrama): tablero unificado para el COE,
 * semáforo de habitabilidad por predio, censo único de damnificados, ayudas sin duplicidad y
 * albergues.
 *
 * Habeas Data: el documento del jefe de hogar se envía solo a la API (que guarda un hash con sal)
 * y se borra del formulario al terminar; nunca se guarda en el navegador.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt, formatTime } from "@/lib/format";
import {
  COLOR_LABEL,
  DAMAGE_LABEL,
  type InspectionColor,
  type InspectionOut,
  type ManzanaRef,
  type PropertyOut,
} from "@/lib/recovery";
import { clearSession, getSession } from "@/lib/session";
import { Albergues } from "./Albergues";
import { Ayudas } from "./Ayudas";
import { Censo } from "./Censo";
import { DetalleRevisiones, Derivaciones, FormatoRevision } from "./FormatoRevision";
import { TableroRecuperacion } from "./TableroRecuperacion";
import { Card, Dot, input } from "./ui";

type Tab = "tablero" | "habitabilidad" | "censo" | "ayudas" | "albergues";

const TABS: { id: Tab; label: string }[] = [
  { id: "tablero", label: "Tablero" },
  { id: "habitabilidad", label: "Habitabilidad" },
  { id: "censo", label: "Censo único" },
  { id: "ayudas", label: "Ayudas" },
  { id: "albergues", label: "Albergues" },
];

// --------------------------------------------------------------------------- habitabilidad

function Habitabilidad({ manzanas, tick }: { manzanas: ManzanaRef[]; tick: number }) {
  const [items, setItems] = useState<PropertyOut[]>([]);
  const [history, setHistory] = useState<{ id: string; visits: InspectionOut[] } | null>(null);
  const [filter, setFilter] = useState<InspectionColor | "">("");
  const [saved, setSaved] = useState(0);

  const load = useCallback(
    () =>
      api
        .GET("/api/v1/recovery/properties", {
          params: { query: filter ? { color: filter } : {} },
        })
        .then(({ data }) => data && setItems(data.items)),
    [filter],
  );

  useEffect(() => {
    void load();
  }, [load, tick, saved]);

  async function openHistory(id: string) {
    if (history?.id === id) {
      setHistory(null);
      return;
    }
    const { data } = await api.GET("/api/v1/recovery/inspections", {
      params: { query: { property_id: id } },
    });
    setHistory({ id, visits: data ?? [] });
  }

  return (
    <div className="flex flex-col gap-4">
      <FormatoRevision manzanas={manzanas} onSaved={() => setSaved((n) => n + 1)} />
      <Derivaciones tick={tick + saved} />

      <Card
        title={`Predios evaluados (${formatInt(items.length)})`}
        extra={
          <select
            className={input}
            value={filter}
            onChange={(e) => setFilter(e.target.value as InspectionColor | "")}
          >
            <option value="">Todos los colores</option>
            {(Object.keys(COLOR_LABEL) as InspectionColor[]).map((c) => (
              <option key={c} value={c}>
                {COLOR_LABEL[c]}
              </option>
            ))}
          </select>
        }
      >
        {items.length === 0 && (
          <p className="text-sm text-tinta-suave">Aún no hay predios evaluados.</p>
        )}
        <ul className="flex flex-col divide-y divide-linea">
          {items.map((p) => (
            <li key={p.property_id} className="py-2 text-sm">
              <button
                type="button"
                onClick={() => openHistory(p.property_id)}
                className="flex w-full flex-wrap items-center gap-2 text-left"
              >
                <Dot color={p.color} />
                <span className="font-medium">{p.property_id}</span>
                <span className="text-tinta-suave">{p.barrio ?? ""}</span>
                <span className="ml-auto text-xs text-tinta-suave">
                  {DAMAGE_LABEL[p.damage_level]} · {p.visits}{" "}
                  {p.visits === 1 ? "visita" : "visitas"} · {formatTime(p.last_at)}
                </span>
              </button>
              {history?.id === p.property_id && (
                <>
                  <ol className="mt-2 ml-5 flex flex-col gap-1 text-xs text-tinta-suave">
                    {history.visits.map((v) => (
                      <li key={v.id} className="flex items-center gap-2">
                        <Dot color={v.color} /> Visita {v.visit_number} · {formatDateTime(v.at)} ·{" "}
                        {DAMAGE_LABEL[v.damage_level]} · {v.inspector_role}
                        {v.notes ? ` · ${v.notes}` : ""}
                      </li>
                    ))}
                  </ol>
                  <DetalleRevisiones propertyId={p.property_id} />
                </>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- panel

export default function PanelRecuperacion() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [tab, setTab] = useState<Tab>("tablero");
  const [manzanas, setManzanas] = useState<ManzanaRef[]>([]);
  const [tick, setTick] = useState(0);
  const allowed = session?.role === "pmu";

  useEffect(() => {
    if (!allowed) {
      router.replace("/ingresar/");
      return;
    }
    api.GET("/api/v1/recovery/manzanas").then(({ data }) => data && setManzanas(data));
  }, [allowed, router]);

  if (!allowed) return null;

  return (
    <div className="flex min-h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-3 text-white">
        <h1 className="font-display text-2xl font-bold">Dacora · Recuperación</h1>
        <EtiquetaSimulado />
        <nav className="ml-auto flex items-center gap-4 text-sm">
          <Link href="/pmu/" className="underline decoration-white/40 underline-offset-4">
            Tablero PMU
          </Link>
          <Link href="/agencia/" className="underline decoration-white/40 underline-offset-4">
            Despachos por agencia
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
      <div
        role="tablist"
        className="flex gap-1 overflow-x-auto border-b border-linea bg-white px-4"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            onClick={() => {
              setTab(t.id);
              setTick((n) => n + 1);
            }}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
              tab === t.id ? "border-sangre font-semibold text-sangre" : "border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <main
        className={`mx-auto flex w-full flex-col gap-4 px-4 py-6 ${tab === "tablero" ? "max-w-6xl" : "max-w-5xl"}`}
      >
        {tab === "tablero" && <TableroRecuperacion />}
        {tab === "habitabilidad" && <Habitabilidad manzanas={manzanas} tick={tick} />}
        {tab === "censo" && <Censo manzanas={manzanas} tick={tick} />}
        {tab === "ayudas" && <Ayudas tick={tick} />}
        {tab === "albergues" && <Albergues tick={tick} />}
      </main>
    </div>
  );
}
