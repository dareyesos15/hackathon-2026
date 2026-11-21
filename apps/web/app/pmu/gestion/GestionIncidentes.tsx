"use client";
/**
 * Gestión de incidentes (PMU y COE): bandeja de incidentes sin asignar, asignar incidentes a una
 * alerta masiva o desacoplarlos a la operación ordinaria, crear incidentes a mano (sin reportes
 * ciudadanos) y activar o cerrar alertas masivas. Todo queda en la bitácora con rol y hora.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { FormularioActivacion } from "@/components/SesionAlertaMasiva";
import { api } from "@/lib/api/client";
import { formatDateTime, formatTime } from "@/lib/format";
import {
  CATEGORY_LABEL,
  STATUS_LABEL,
  TRIAGE_COLOR,
  TRIAGE_LABEL,
  TRIAGE_ORDER,
  type Category,
  type IncidentSummary,
  type TriageLevel,
} from "@/lib/labels";
import { useLiveIncidents } from "@/lib/live";
import {
  MASS_EVENT_LABEL,
  ORDINARY,
  UNASSIGNED,
  sessionOf,
  useMassAlerts,
  type MassAlertOut,
  type SessionId,
} from "@/lib/massAlerts";
import { useOfflineData } from "@/lib/offline";
import { clearSession, getSession } from "@/lib/session";

type FC = GeoJSON.FeatureCollection & { names?: string[] };

const CATEGORIES = (Object.keys(CATEGORY_LABEL) as Category[]).filter(
  (c) => c !== "sin_clasificar",
);
const CLOSED_STATUS = new Set(["atendido", "descartado"]);

function errorText(err: unknown, fallback: string): string {
  return (err as { detail?: string } | undefined)?.detail ?? fallback;
}

function TriajeChip({ level }: { level: TriageLevel }) {
  return (
    <span
      className="inline-block rounded-sm px-1.5 py-0.5 text-xs font-bold text-white"
      style={{ background: TRIAGE_COLOR[level] }}
    >
      {TRIAGE_LABEL[level]}
    </span>
  );
}

// ------------------------------------------------------------------ alertas masivas

function TarjetaAlerta({
  alert,
  openCount,
  lifeOpen,
  onClosed,
}: {
  alert: MassAlertOut;
  openCount: number;
  lifeOpen: number;
  onClosed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function close(deleteIncidents: boolean) {
    if (deleteIncidents) {
      const ok = window.confirm(
        `Se cerrará "${alert.title}" y se ELIMINARÁN sus ${alert.incidents_total} incidentes ` +
          `(con reportes, bitácora y despachos)` +
          (lifeOpen > 0 ? `, incluidos ${lifeOpen} abiertos con riesgo vital` : "") +
          ". El reporte final conserva su trazabilidad. Esta acción no se puede deshacer. ¿Continuar?",
      );
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    const {
      data,
      error: err,
      response,
    } = await api.POST("/api/v1/mass-alerts/{mass_alert_id}/close", {
      params: { path: { mass_alert_id: alert.id } },
      body: { delete_incidents: deleteIncidents },
    });
    setBusy(false);
    if (data) {
      setBlocked(null);
      onClosed();
      return;
    }
    const message = errorText(err, "No se pudo cerrar la alerta");
    if (
      response.status === 409 &&
      (err as { code?: string } | undefined)?.code === "open_incidents"
    ) {
      setBlocked(message);
    } else {
      setError(message);
    }
  }

  return (
    <li className="rounded-md border border-senal/40 bg-white p-3">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="inline-block h-2 w-2 rounded-full bg-senal" />
        <span className="font-display text-lg font-semibold">{alert.title}</span>
        <span className="text-xs text-tinta-suave">
          {MASS_EVENT_LABEL[alert.event_type]} · desde {formatDateTime(alert.started_at)}
        </span>
      </div>
      <p className="mt-1 text-sm tabular-nums">
        {alert.incidents_total} incidentes · {alert.incidents_closed} cerrados ·{" "}
        <span className={openCount > 0 ? "font-bold text-senal" : ""}>{openCount} abiertos</span>
      </p>
      <div className="mt-2 flex flex-wrap gap-2 text-sm">
        <Link
          href={`/pmu/?sesion=${alert.id}`}
          className="rounded border border-linea px-2 py-1 hover:bg-papel"
        >
          Ver en el tablero
        </Link>
        <Link
          href={`/pmu/alerta-masiva/?id=${alert.id}`}
          className="rounded border border-linea px-2 py-1 hover:bg-papel"
        >
          Reporte preliminar
        </Link>
        <button
          type="button"
          disabled={busy}
          onClick={() => close(false)}
          className="rounded bg-sangre px-2 py-1 font-bold text-white hover:bg-sangre-claro disabled:opacity-60"
        >
          Cerrar alerta
        </button>
      </div>
      {blocked && (
        <div className="mt-2 rounded border border-senal/40 bg-senal-fondo p-2 text-sm">
          <p className="font-medium">Cierre bloqueado.</p>
          <p className="text-tinta-suave">{blocked}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => close(true)}
            className="mt-2 rounded bg-senal px-2 py-1 font-bold text-white hover:bg-[#b51723] disabled:opacity-60"
          >
            Cerrar y eliminar los {alert.incidents_total} incidentes asociados
          </button>
        </div>
      )}
      {error && <p className="mt-2 text-sm font-medium text-senal">{error}</p>}
    </li>
  );
}

// ------------------------------------------------------------------ crear incidente

function FormularioIncidente({
  barrios,
  active,
  defaultTarget,
  onCreated,
}: {
  barrios: string[];
  active: MassAlertOut[];
  defaultTarget: string;
  onCreated: (incident: IncidentSummary) => void;
}) {
  const [category, setCategory] = useState<Category>("dano_estructural");
  const [triage, setTriage] = useState<TriageLevel | "">("");
  const [barrio, setBarrio] = useState("");
  const [coords, setCoords] = useState("");
  const [people, setPeople] = useState("");
  const [description, setDescription] = useState("");
  const [target, setTarget] = useState(defaultTarget);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<IncidentSummary | null>(null);
  const targetValid = target === ORDINARY || active.some((a) => a.id === target);
  const effectiveTarget = targetValid ? target : ORDINARY;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    let lat: number | null = null;
    let lon: number | null = null;
    if (coords.trim()) {
      const parts = coords.split(",").map((p) => Number(p.trim()));
      if (parts.length !== 2 || parts.some((n) => Number.isNaN(n))) {
        setError("Coordenadas en formato lat, lon (por ejemplo 5.0689, -75.5174)");
        return;
      }
      [lat, lon] = parts;
    }
    if (!barrio && lat === null) {
      setError("Indique el barrio o las coordenadas");
      return;
    }
    setBusy(true);
    const { data, error: err } = await api.POST("/api/v1/incidents", {
      body: {
        category,
        description: description.trim(),
        triage_level: triage || null,
        barrio: barrio || null,
        lat,
        lon,
        people_affected: people ? Number(people) : null,
        mass_alert_id: effectiveTarget === ORDINARY ? null : effectiveTarget,
      },
    });
    setBusy(false);
    if (data) {
      setCreated(data);
      setDescription("");
      setPeople("");
      setCoords("");
      onCreated(data);
    } else {
      setError(errorText(err, "No se pudo crear el incidente"));
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2 text-sm">
      <label className="flex flex-col gap-1">
        <span className="font-medium">Categoría</span>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
          className="rounded border border-linea bg-white px-2 py-1"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c]}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Nivel de triaje</span>
        <select
          value={triage}
          onChange={(e) => setTriage(e.target.value as TriageLevel | "")}
          className="rounded border border-linea bg-white px-2 py-1"
        >
          <option value="">Según la categoría (matriz de triaje)</option>
          {TRIAGE_ORDER.map((t) => (
            <option key={t} value={t}>
              {TRIAGE_LABEL[t]}
            </option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1">
          <span className="font-medium">Barrio</span>
          <select
            value={barrio}
            onChange={(e) => setBarrio(e.target.value)}
            className="rounded border border-linea bg-white px-2 py-1"
          >
            <option value="">—</option>
            {barrios.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">o lat, lon</span>
          <input
            value={coords}
            onChange={(e) => setCoords(e.target.value)}
            placeholder="5.0689, -75.5174"
            className="rounded border border-linea bg-white px-2 py-1"
          />
        </label>
      </div>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Personas afectadas (opcional)</span>
        <input
          type="number"
          min={0}
          value={people}
          onChange={(e) => setPeople(e.target.value)}
          className="rounded border border-linea bg-white px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Descripción</span>
        <textarea
          required
          minLength={3}
          maxLength={1000}
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Qué pasa y dónde (p. ej. informado por radio de Bomberos)"
          className="rounded border border-linea bg-white px-2 py-1"
        />
        <span className="text-xs text-tinta-suave">
          Se quitan teléfonos, cédulas, correos y nombres antes de guardar (Ley 1581).
        </span>
      </label>
      <label className="flex flex-col gap-1">
        <span className="font-medium">Sesión</span>
        <select
          value={effectiveTarget}
          onChange={(e) => setTarget(e.target.value)}
          className="rounded border border-linea bg-white px-2 py-1"
        >
          <option value={ORDINARY}>Operación ordinaria</option>
          {active.map((a) => (
            <option key={a.id} value={a.id}>
              Alerta masiva: {a.title}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="font-medium text-senal">{error}</p>}
      <button
        type="submit"
        disabled={busy}
        className="rounded bg-sangre px-3 py-1.5 font-bold text-white hover:bg-sangre-claro disabled:opacity-60"
      >
        {busy ? "Creando…" : "Crear incidente"}
      </button>
      {created && (
        <p className="rounded bg-verificado/10 px-2 py-1 text-verificado">
          Incidente creado ({CATEGORY_LABEL[created.category]}, {TRIAGE_LABEL[created.triage_level]}
          ).{" "}
          <Link
            href={`/pmu/?sesion=${sessionOf(created)}&incidente=${created.id}`}
            className="font-medium underline"
          >
            Abrir en el tablero
          </Link>
        </p>
      )}
    </form>
  );
}

// ------------------------------------------------------------------ panel

export default function GestionIncidentes() {
  const router = useRouter();
  const [session] = useState(getSession);
  const token = session?.role === "pmu" ? session.token : null;
  const live = useLiveIncidents(token);
  const massAlerts = useMassAlerts(Boolean(token), live.massAlertRevision);
  const barrios = useOfflineData<FC>(
    "barrios",
    async () => (await api.GET("/api/v1/geo/barrios")).data as unknown as FC | undefined,
  ).data;
  const barrioNames = useMemo(() => (barrios?.names ?? []).slice(), [barrios]);

  const all = useMemo(
    () =>
      Array.from(live.incidents.values()).sort(
        (a, b) =>
          TRIAGE_ORDER.indexOf(a.triage_level) - TRIAGE_ORDER.indexOf(b.triage_level) ||
          b.updated_at.localeCompare(a.updated_at),
      ),
    [live.incidents],
  );
  const bySession = useMemo(() => {
    const map = new Map<SessionId, IncidentSummary[]>();
    for (const i of all) {
      const key = sessionOf(i);
      map.set(key, [...(map.get(key) ?? []), i]);
    }
    return map;
  }, [all]);
  const unassigned = bySession.get(UNASSIGNED) ?? [];

  const [view, setView] = useState<SessionId | null>(null);
  const currentView: SessionId = view ?? (unassigned.length > 0 ? UNASSIGNED : ORDINARY);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [moveTo, setMoveTo] = useState<string>("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [activating, setActivating] = useState(false);

  const active = massAlerts.active;
  const closedAlerts = massAlerts.items.filter((a) => a.status !== "activa");
  const viewAlert = massAlerts.items.find((a) => a.id === currentView) ?? null;
  const readOnly = viewAlert !== null && viewAlert.status !== "activa";
  const rows = (bySession.get(currentView) ?? []).filter((i) => {
    if (!filter.trim()) return true;
    const q = filter.trim().toLowerCase();
    return (
      CATEGORY_LABEL[i.category].toLowerCase().includes(q) ||
      (i.barrio ?? "").toLowerCase().includes(q) ||
      TRIAGE_LABEL[i.triage_level].toLowerCase().includes(q)
    );
  });
  const moveTargets: { id: string; label: string }[] = [
    { id: ORDINARY, label: "Operación ordinaria (desacoplar)" },
    ...active.map((a) => ({ id: a.id, label: `Alerta masiva: ${a.title}` })),
  ].filter((t) => t.id !== currentView);
  const effectiveMoveTo = moveTargets.some((t) => t.id === moveTo)
    ? moveTo
    : (moveTargets[0]?.id ?? "");

  useEffect(() => {
    if (!token) router.replace("/ingresar/");
  }, [token, router]);

  if (!token) return null;

  function changeView(next: SessionId) {
    setView(next);
    setSelected(new Set());
    setMessage(null);
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function move() {
    const ids = rows.filter((r) => selected.has(r.id)).map((r) => r.id);
    if (ids.length === 0 || !effectiveMoveTo) return;
    setBusy(true);
    setMessage(null);
    const { data, error } = await api.POST("/api/v1/incidents/assign", {
      body: {
        incident_ids: ids,
        mass_alert_id: effectiveMoveTo === ORDINARY ? null : effectiveMoveTo,
      },
    });
    setBusy(false);
    if (data) {
      const target = moveTargets.find((t) => t.id === effectiveMoveTo)?.label ?? "";
      setMessage({ ok: true, text: `${data.items.length} incidentes movidos a ${target}.` });
      setSelected(new Set());
    } else {
      setMessage({ ok: false, text: errorText(error, "No se pudieron mover los incidentes") });
    }
  }

  const tabs: { id: SessionId; label: string; count: number; tone?: string }[] = [
    ...(active.length > 0 || unassigned.length > 0
      ? [
          {
            id: UNASSIGNED,
            label: "Sin asignar",
            count: unassigned.length,
            tone: unassigned.length > 0 ? "bg-[#ffd27a] text-tinta" : undefined,
          },
        ]
      : []),
    { id: ORDINARY, label: "Operación ordinaria", count: bySession.get(ORDINARY)?.length ?? 0 },
    ...active.map((a) => ({
      id: a.id,
      label: `● ${a.title}`,
      count: bySession.get(a.id)?.length ?? 0,
    })),
  ];

  return (
    <div className="min-h-screen bg-papel">
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-2 text-white">
        <h1 className="font-display text-2xl font-semibold leading-none">Dacora</h1>
        <span className="text-sm text-white/75">
          Gestión de incidentes{session ? ` · ${session.displayName}` : ""}
        </span>
        <EtiquetaSimulado sobreOscuro />
        <nav className="ml-auto flex items-center gap-4 text-sm">
          <Link href="/pmu/" className="underline decoration-white/40 underline-offset-4">
            Tablero PMU
          </Link>
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

      <main className="grid gap-4 px-4 py-4 lg:grid-cols-[1fr_380px]">
        <section className="flex min-w-0 flex-col gap-3">
          {unassigned.length > 0 && (
            <div className="rounded-md border border-[#e8a92a] bg-[#fff6df] px-3 py-2 text-sm">
              <span className="font-bold">{unassigned.length} incidentes sin asignar.</span>{" "}
              Llegaron mientras hay alertas masivas activas: elija a qué alerta pertenecen o
              desacóplelos a la operación ordinaria.
            </div>
          )}
          <nav className="flex flex-wrap gap-1">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => changeView(t.id)}
                className={`rounded px-2.5 py-1 text-sm font-medium ${
                  currentView === t.id
                    ? "bg-slate-900 text-white"
                    : `${t.tone ?? "bg-white text-slate-700"} shadow-sm`
                }`}
              >
                {t.label} <span className="tabular-nums opacity-75">({t.count})</span>
              </button>
            ))}
            {closedAlerts.length > 0 && (
              <select
                value={readOnly ? currentView : ""}
                onChange={(e) => e.target.value && changeView(e.target.value)}
                className="rounded border border-linea bg-white px-2 py-1 text-sm"
              >
                <option value="">Alertas cerradas…</option>
                {closedAlerts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title}
                  </option>
                ))}
              </select>
            )}
          </nav>

          <div className="flex flex-wrap items-center gap-2 rounded-md border border-linea bg-white px-3 py-2 text-sm">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filtrar por categoría, barrio o triaje"
              className="min-w-48 flex-1 rounded border border-linea px-2 py-1"
            />
            {readOnly ? (
              <span className="text-tinta-suave">
                Alerta cerrada: sus incidentes no se mueven.{" "}
                <Link
                  href={`/pmu/alerta-masiva/?id=${currentView}`}
                  className="font-medium underline"
                >
                  Ver reporte final
                </Link>
              </span>
            ) : (
              <>
                <span className="text-tinta-suave">{selected.size} seleccionados · mover a</span>
                <select
                  value={effectiveMoveTo}
                  onChange={(e) => setMoveTo(e.target.value)}
                  className="rounded border border-linea bg-white px-2 py-1"
                >
                  {moveTargets.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy || selected.size === 0 || !effectiveMoveTo}
                  onClick={move}
                  className="rounded bg-sangre px-3 py-1 font-bold text-white hover:bg-sangre-claro disabled:opacity-50"
                >
                  Mover
                </button>
              </>
            )}
          </div>
          {message && (
            <p className={`text-sm font-medium ${message.ok ? "text-verificado" : "text-senal"}`}>
              {message.text}
            </p>
          )}

          <div className="overflow-x-auto rounded-md border border-linea bg-white">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="bg-papel text-left text-xs text-tinta-suave">
                <tr>
                  <th className="w-8 px-2 py-1.5">
                    {!readOnly && (
                      <input
                        type="checkbox"
                        aria-label="Seleccionar todos"
                        checked={rows.length > 0 && rows.every((r) => selected.has(r.id))}
                        onChange={(e) =>
                          setSelected(e.target.checked ? new Set(rows.map((r) => r.id)) : new Set())
                        }
                      />
                    )}
                  </th>
                  <th className="px-2 font-normal">Triaje</th>
                  <th className="px-2 font-normal">Incidente</th>
                  <th className="px-2 font-normal">Barrio</th>
                  <th className="px-2 font-normal">Estado</th>
                  <th className="px-2 text-right font-normal">Reportes</th>
                  <th className="px-2 text-right font-normal">Veracidad</th>
                  <th className="px-2 font-normal">Actualizado</th>
                  <th className="px-2 font-normal" />
                </tr>
              </thead>
              <tbody>
                {rows.map((i) => (
                  <tr
                    key={i.id}
                    className={`border-t border-linea ${selected.has(i.id) ? "bg-senal-fondo" : ""}`}
                  >
                    <td className="px-2 py-1.5">
                      {!readOnly && (
                        <input
                          type="checkbox"
                          aria-label="Seleccionar incidente"
                          checked={selected.has(i.id)}
                          onChange={() => toggle(i.id)}
                        />
                      )}
                    </td>
                    <td className="px-2">
                      <TriajeChip level={i.triage_level} />
                    </td>
                    <td className="px-2">
                      {CATEGORY_LABEL[i.category]}
                      {i.is_life_threat && !CLOSED_STATUS.has(i.status) && (
                        <span className="ml-1 text-xs text-senal">● vital</span>
                      )}
                      {i.source.includes("manual") && (
                        <span className="ml-1 rounded-sm bg-papel px-1 text-xs text-tinta-suave">
                          manual
                        </span>
                      )}
                    </td>
                    <td className="px-2">{i.barrio ?? "Sin ubicar"}</td>
                    <td className="px-2">{STATUS_LABEL[i.status]}</td>
                    <td className="px-2 text-right tabular-nums">{i.report_count}</td>
                    <td className="px-2 text-right tabular-nums">{i.trust_score}</td>
                    <td className="px-2 tabular-nums text-tinta-suave">
                      {formatTime(i.updated_at)}
                    </td>
                    <td className="px-2 text-right">
                      <Link
                        href={`/pmu/?sesion=${sessionOf(i)}&incidente=${i.id}`}
                        className="text-xs font-medium underline underline-offset-2"
                      >
                        Abrir
                      </Link>
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-3 py-6 text-center text-tinta-suave">
                      No hay incidentes en esta sesión.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="flex flex-col gap-4">
          <section className="rounded-md border border-linea bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="font-display text-xl font-semibold">Alertas masivas</h2>
              {!activating && (
                <button
                  type="button"
                  onClick={() => setActivating(true)}
                  className="rounded border border-senal px-2 py-1 text-sm font-bold text-senal hover:bg-senal-fondo"
                >
                  Activar
                </button>
              )}
            </div>
            {activating && (
              <div className="-mx-3 mb-3">
                <FormularioActivacion
                  onCancel={() => setActivating(false)}
                  onCreated={() => setActivating(false)}
                />
              </div>
            )}
            {active.length === 0 ? (
              <p className="text-sm text-tinta-suave">
                No hay alertas masivas activas: los incidentes nuevos entran a la operación
                ordinaria.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {active.map((a) => {
                  const list = bySession.get(a.id) ?? [];
                  const open = list.filter((i) => !CLOSED_STATUS.has(i.status));
                  return (
                    <TarjetaAlerta
                      key={a.id}
                      alert={a}
                      openCount={open.length}
                      lifeOpen={open.filter((i) => i.is_life_threat).length}
                      onClosed={() => {
                        if (currentView === a.id) changeView(ORDINARY);
                        void live.reload();
                      }}
                    />
                  );
                })}
              </ul>
            )}
            {closedAlerts.length > 0 && (
              <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-tinta-suave">
                  Cerradas ({closedAlerts.length})
                </summary>
                <ul className="mt-1 flex flex-col gap-1">
                  {closedAlerts.map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-2">
                      <span className="truncate">
                        {a.title}
                        <span className="text-xs text-tinta-suave">
                          {" "}
                          · {a.resolved_at ? formatDateTime(a.resolved_at) : ""}
                        </span>
                      </span>
                      <Link
                        href={`/pmu/alerta-masiva/?id=${a.id}`}
                        className="shrink-0 font-medium underline"
                      >
                        Reporte final
                      </Link>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          <section className="rounded-md border border-linea bg-white p-3">
            <h2 className="font-display text-xl font-semibold">Crear incidente</h2>
            <p className="mb-2 text-xs text-tinta-suave">
              Sin reporte ciudadano (radio, llamada directa, recorrido). Nace verificado y queda en
              la bitácora con su rol.
            </p>
            <FormularioIncidente
              key={active.map((a) => a.id).join(",")}
              barrios={barrioNames}
              active={active}
              defaultTarget={viewAlert && !readOnly ? viewAlert.id : ORDINARY}
              onCreated={() => setMessage(null)}
            />
          </section>
        </aside>
      </main>
    </div>
  );
}
