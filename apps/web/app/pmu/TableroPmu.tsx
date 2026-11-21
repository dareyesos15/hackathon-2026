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
import { useOfflineData } from "@/lib/offline";
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
  // Mapa base: guardado en el dispositivo para seguir viéndolo sin conexión.
  const barrios = useOfflineData<FC>(
    "barrios",
    async () => (await api.GET("/api/v1/geo/barrios")).data as unknown as FC | undefined,
  ).data;
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
  const cascadeData = useOfflineData<CascadeLayer>(
    "cascade",
    async () => (await api.GET("/api/v1/map/cascade")).data as CascadeLayer | undefined,
    { enabled: Boolean(token) && cascadeOn, refreshKey: live.cascadeRevision },
  );
  const cascade = cascadeData.data;
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
    if (!token) router.replace("/ingresar/");
  }, [token, router]);

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
          <span className="text-sm text-white/75">
            Tablero del PMU{session?.role === "coe" ? " · COE" : ""}
          </span>
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

      <div className="px-4 pt-2">
        <AvisoAlerta alerts={alertsFromGeoJSON(activeAlerts)} />
      </div>

      <section className="grid grid-cols-2 gap-2 px-4 py-3 md:grid-cols-5">
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
        <div className="min-h-[420px] overflow-hidden rounded-md border border-linea bg-white">
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
                offline={cascadeData.offline}
                savedAt={cascadeData.savedAt}
              />
            )}
          </div>
        </aside>
      </main>
    </div>
  );
}
