"use client";
/**
 * Tablero situacional del PMU. Solo en el navegador: usa sessionStorage, SSE y MapLibre.
 * specs/002: despacho y recorridos (US1), bandeja de alertas y alertas vigentes (US2) y capa de
 * efectos en cascada (US3). El COE usa el mismo tablero y además aprueba alertas.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Cifra } from "@/components/Cifra";
import { DetalleIncidente } from "@/components/DetalleIncidente";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { Mapa } from "@/components/Mapa";
import { AvisoAlerta, alertsFromGeoJSON } from "@/components/AvisoAlerta";
import { BandejaAlertas } from "@/components/BandejaAlertas";
import {
  CapaCascada,
  selectionFrom,
  type CascadeLayer,
  type CascadeSelection,
} from "@/components/CapaCascada";
import { EditorAlerta } from "@/components/EditorAlerta";
import { MatrizTriaje } from "@/components/MatrizTriaje";
import {
  circlePreview,
  draftFromIncident,
  draftFromManzana,
  emptyDraft,
  type AlertDraft,
} from "@/lib/alerts";
import { api } from "@/lib/api/client";
import { resourcesToGeoJSON, trailsToGeoJSON } from "@/lib/dispatch";
import type { AlertOut } from "@/lib/labels";
import { useLiveIncidents } from "@/lib/live";
import { clearSession, getSession } from "@/lib/session";
import { kpiMap, useKpi } from "@/lib/useKpi";

type FC = GeoJSON.FeatureCollection;
type Tab = "triaje" | "alertas" | "cascada";

const TAB_LABEL: Record<Tab, string> = {
  triaje: "Triaje",
  alertas: "Alertas",
  cascada: "Cascada",
};

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
  const token = session?.role === "operador_pmu" || session?.role === "coe" ? session.token : null;
  const live = useLiveIncidents(token);
  const kpis = kpiMap(useKpi(live.kpiRevision + Math.floor(live.revision / 10)));
  const incidents = useMemo(() => Array.from(live.incidents.values()), [live.incidents]);
  const resourcesFc = useMemo(() => resourcesToGeoJSON(live.resources.values()), [live.resources]);
  const trailsFc = useMemo(() => trailsToGeoJSON(live.trails), [live.trails]);
  const isCoe = session?.role === "coe";
  const [tab, setTab] = useState<Tab>("triaje");
  const [activeAlerts, setActiveAlerts] = useState<FC | null>(null);
  const [draft, setDraft] = useState<AlertDraft | null>(null);
  const [editing, setEditing] = useState<AlertOut | null>(null);
  const [picking, setPicking] = useState(false);
  const [cascadeOn, setCascadeOn] = useState(false);
  const [cascade, setCascade] = useState<CascadeLayer | null>(null);
  const [cascadeSel, setCascadeSel] = useState<CascadeSelection | null>(null);
  const barrioNames = useMemo(
    () => ((barrios as (FC & { names?: string[] }) | null)?.names ?? []).slice(),
    [barrios],
  );

  // Alertas vigentes: se refrescan con cada evento `alert.changed` (o en el modo de respaldo).
  useEffect(() => {
    if (!token) return;
    let active = true;
    api.GET("/api/v1/alerts/active").then(({ data }) => {
      if (active && data) setActiveAlerts(data as unknown as FC);
    });
    return () => {
      active = false;
    };
  }, [token, live.alertRevision]);

  // Capa de cascada: solo si está activa; se recalcula con `cascade.invalidated`.
  useEffect(() => {
    if (!token || !cascadeOn) return;
    let active = true;
    api.GET("/api/v1/map/cascade").then(({ data }) => {
      if (active && data) setCascade(data as unknown as CascadeLayer);
    });
    return () => {
      active = false;
    };
  }, [token, cascadeOn, live.cascadeRevision]);

  const alertAreasFc = useMemo<FC | null>(() => {
    const preview = draft?.circle ? circlePreview(draft.circle).features : [];
    return {
      type: "FeatureCollection",
      features: [...(activeAlerts?.features ?? []), ...preview],
    };
  }, [activeAlerts, draft]);

  function openEditor(next: AlertDraft, existing: AlertOut | null = null) {
    setDraft(next);
    setEditing(existing);
    setPicking(false);
    setTab("alertas");
    select(null);
  }

  function editExisting(alert: AlertOut) {
    openEditor(
      {
        type: alert.type,
        barrios: alert.area_barrios,
        circle: alert.area_circle
          ? {
              lat: alert.area_circle.lat,
              lon: alert.area_circle.lon,
              radius_m: alert.area_circle.radius_m,
            }
          : null,
        message: alert.message,
        channels: alert.channels,
      },
      alert,
    );
  }

  function closeEditor() {
    setDraft(null);
    setEditing(null);
    setPicking(false);
  }

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
        <h1 className="text-lg font-bold">
          Dacora · Tablero PMU{session?.role === "coe" ? " · COE" : ""}
        </h1>
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

      <div className="px-4 pt-2">
        <AvisoAlerta alerts={alertsFromGeoJSON(activeAlerts)} />
      </div>

      <section className="grid grid-cols-2 gap-2 px-4 py-2 md:grid-cols-5">
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
        {kpis.critical_without_dispatch && (
          <Cifra
            etiqueta="Críticos sin despacho"
            valor={kpis.critical_without_dispatch.value ?? null}
            unidad="conteo"
            fuente={kpis.critical_without_dispatch.source}
            version={kpis.critical_without_dispatch.version}
            corte={kpis.critical_without_dispatch.cutoff_at}
            meta="0"
            estado={(kpis.critical_without_dispatch.value ?? 0) > 0 ? "alerta" : "ok"}
            simulado
          />
        )}
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
            resources={resourcesFc}
            trails={trailsFc}
            alertAreas={alertAreasFc}
            cascade={cascadeOn ? cascade : null}
            onCascadeSelect={(props) => setCascadeSel(selectionFrom(props, cascade))}
            onMapClick={
              picking && draft
                ? (lat, lon) => {
                    setDraft({
                      ...draft,
                      barrios: [],
                      circle: { lat, lon, radius_m: draft.circle?.radius_m ?? 300 },
                    });
                    setPicking(false);
                  }
                : undefined
            }
          />
        </div>
        <aside className="flex flex-col gap-2 overflow-hidden">
          <nav className="flex gap-1">
            {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => {
                  setTab(t);
                  if (t !== "triaje") select(null);
                }}
                className={`flex-1 rounded px-2 py-1 text-sm font-medium ${
                  tab === t ? "bg-slate-900 text-white" : "bg-white text-slate-700 shadow-sm"
                }`}
              >
                {TAB_LABEL[t]}
              </button>
            ))}
          </nav>
          <div className="flex-1 overflow-y-auto">
            {tab === "triaje" &&
              (selectedId ? (
                <DetalleIncidente
                  key={selectedId}
                  incidentId={selectedId}
                  incidents={incidents}
                  revision={live.revision}
                  onClose={() => select(null)}
                  onSelect={select}
                  onCreateAlert={(incident) => openEditor(draftFromIncident(incident))}
                />
              ) : (
                <MatrizTriaje incidents={incidents} selectedId={selectedId} onSelect={select} />
              ))}
            {tab === "alertas" &&
              (draft ? (
                <EditorAlerta
                  draft={draft}
                  existing={editing}
                  barrioNames={barrioNames}
                  picking={picking}
                  onPickCenter={() => setPicking((p) => !p)}
                  onChange={setDraft}
                  onClose={closeEditor}
                  onSaved={closeEditor}
                />
              ) : (
                <BandejaAlertas
                  isCoe={isCoe}
                  revision={live.alertRevision}
                  onEdit={editExisting}
                  onNew={() => openEditor(emptyDraft())}
                />
              ))}
            {tab === "cascada" && (
              <CapaCascada
                enabled={cascadeOn}
                onToggle={(on) => {
                  setCascadeOn(on);
                  if (!on) setCascadeSel(null);
                }}
                layer={cascade}
                selected={cascadeSel}
                onCreateAlert={(sel) => openEditor(draftFromManzana(sel))}
              />
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
