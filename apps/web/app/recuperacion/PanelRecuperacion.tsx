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
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { API_BASE, api } from "@/lib/api/client";
import { DEMO_MODE } from "@/lib/env";
import { formatDateTime, formatInt, formatTime } from "@/lib/format";
import {
  AID_LABEL,
  COLOR_DAMAGE,
  COLOR_LABEL,
  DAMAGE_LABEL,
  RUD_LABEL,
  VULN_LABEL,
  errorText,
  type AidOut,
  type AidType,
  type DamageLevel,
  type HouseholdOut,
  type InspectionColor,
  type InspectionOut,
  type ManzanaRef,
  type PropertyOut,
  type ShelterOut,
} from "@/lib/recovery";
import { clearSession, getSession } from "@/lib/session";
import { TableroRecuperacion } from "./TableroRecuperacion";
import {
  Card,
  Dot,
  EMPTY_PROPERTY,
  Notice,
  PropertyFields,
  button,
  input,
  propertyBody,
} from "./ui";

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
  const [property, setProperty] = useState(EMPTY_PROPERTY);
  const [color, setColor] = useState<InspectionColor>("amarillo");
  const [damage, setDamage] = useState<DamageLevel>("mediano_uso_restringido");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const [items, setItems] = useState<PropertyOut[]>([]);
  const [history, setHistory] = useState<{ id: string; visits: InspectionOut[] } | null>(null);
  const [filter, setFilter] = useState<InspectionColor | "">("");

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
  }, [load, tick]);

  function pickColor(c: InspectionColor) {
    setColor(c);
    if (!COLOR_DAMAGE[c].includes(damage)) setDamage(COLOR_DAMAGE[c][0]);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const { data, error } = await api.POST("/api/v1/recovery/inspections", {
      body: { ...propertyBody(property), color, damage_level: damage, notes: notes.trim() || null },
    });
    if (error || !data) {
      setMsg({ tone: "error", text: errorText(error, "No se pudo guardar la evaluación") });
      return;
    }
    setMsg(
      data.visit_number > 1
        ? {
            tone: "warn",
            text: `Predio ya evaluado: esta es la visita n.º ${data.visit_number}. Se unió al mismo predio (${data.property_id}).`,
          }
        : { tone: "ok", text: `Evaluación registrada para ${data.property_id}.` },
    );
    setNotes("");
    await load();
  }

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
      <Card title="Nueva evaluación de habitabilidad">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <PropertyFields manzanas={manzanas} value={property} onChange={setProperty} />
          <fieldset className="flex flex-wrap gap-2">
            <legend className="mb-1 text-xs text-tinta-suave">Semáforo</legend>
            {(Object.keys(COLOR_LABEL) as InspectionColor[]).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => pickColor(c)}
                aria-pressed={color === c}
                className={`flex items-center gap-2 rounded border px-3 py-1.5 text-sm ${
                  color === c ? "border-tinta font-semibold" : "border-linea"
                }`}
              >
                <Dot color={c} /> {COLOR_LABEL[c]}
              </button>
            ))}
          </fieldset>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Nivel de daño (NSR-10)
              <select
                className={input}
                value={damage}
                onChange={(e) => setDamage(e.target.value as DamageLevel)}
              >
                {COLOR_DAMAGE[color].map((d) => (
                  <option key={d} value={d}>
                    {DAMAGE_LABEL[d]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Observaciones (sin nombres ni teléfonos)
              <input className={input} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </label>
          </div>
          <div>
            <button type="submit" className={button}>
              Registrar evaluación
            </button>
          </div>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </form>
      </Card>

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
                <ol className="mt-2 ml-5 flex flex-col gap-1 text-xs text-tinta-suave">
                  {history.visits.map((v) => (
                    <li key={v.id} className="flex items-center gap-2">
                      <Dot color={v.color} /> Visita {v.visit_number} · {formatDateTime(v.at)} ·{" "}
                      {DAMAGE_LABEL[v.damage_level]} · {v.inspector_role}
                      {v.notes ? ` · ${v.notes}` : ""}
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- censo

function Censo({ manzanas, tick }: { manzanas: ManzanaRef[]; tick: number }) {
  const [document, setDocument] = useState("");
  const [members, setMembers] = useState(1);
  const [pets, setPets] = useState(0);
  const [property, setProperty] = useState(EMPTY_PROPERTY);
  const [vuln, setVuln] = useState({
    children: false,
    elderly: false,
    disability: false,
    pregnancy: false,
  });
  const [msg, setMsg] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const [items, setItems] = useState<HouseholdOut[]>([]);

  const load = useCallback(
    () => api.GET("/api/v1/recovery/households").then(({ data }) => data && setItems(data.items)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const { data, error } = await api.POST("/api/v1/recovery/households", {
      body: {
        ...propertyBody(property),
        document,
        members_count: members,
        pets_count: pets,
        rud_status: "pendiente",
        vulnerability: vuln,
      },
    });
    setDocument("");
    if (error || !data) {
      setMsg({ tone: "error", text: errorText(error, "No se pudo registrar el hogar") });
      return;
    }
    setMsg(
      data.created
        ? { tone: "ok", text: `Hogar ${data.household.code} registrado en el censo único.` }
        : {
            tone: "warn",
            text: `Este hogar ya estaba registrado (código ${data.household.code}). No se creó un duplicado.`,
          },
    );
    await load();
  }

  async function inscribir(h: HouseholdOut) {
    await api.PATCH("/api/v1/recovery/households/{household_id}/rud", {
      params: { path: { household_id: h.id }, query: { rud_status: "inscrito" } },
    });
    await load();
  }

  async function exportCsv() {
    const token = getSession()?.token ?? "";
    const res = await fetch(`${API_BASE}/api/v1/recovery/households/export.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const url = URL.createObjectURL(await res.blob());
    const a = window.document.createElement("a");
    a.href = url;
    a.download = "censo_rud.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-4">
      <Card title="Registrar hogar damnificado">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <p className="text-xs text-tinta-suave">
            El documento del jefe de hogar solo se usa para evitar registros duplicados: Dacora
            guarda un código cifrado (HMAC con sal) y nunca el número (Ley 1581 de 2012).
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Documento del jefe de hogar
              <input
                className={input}
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                autoComplete="off"
                inputMode="numeric"
                required
                minLength={5}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Integrantes
              <input
                type="number"
                min={1}
                max={30}
                className={input}
                value={members}
                onChange={(e) => setMembers(Number(e.target.value))}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Mascotas
              <input
                type="number"
                min={0}
                max={30}
                className={input}
                value={pets}
                onChange={(e) => setPets(Number(e.target.value))}
              />
            </label>
          </div>
          <PropertyFields manzanas={manzanas} value={property} onChange={setProperty} optional />
          <fieldset className="flex flex-wrap gap-3 text-sm">
            <legend className="mb-1 text-xs text-tinta-suave">
              Vulnerabilidad (dato sensible: acceso restringido)
            </legend>
            {(Object.keys(VULN_LABEL) as (keyof typeof VULN_LABEL)[]).map((k) => (
              <label key={k} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={vuln[k]}
                  onChange={(e) => setVuln({ ...vuln, [k]: e.target.checked })}
                />
                {VULN_LABEL[k]}
              </label>
            ))}
          </fieldset>
          <div>
            <button type="submit" className={button} disabled={document.trim().length < 5}>
              Registrar hogar
            </button>
          </div>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </form>
      </Card>

      <Card
        title={`Censo único (${formatInt(items.length)} hogares)`}
        extra={
          <button
            type="button"
            onClick={exportCsv}
            className="rounded border border-linea px-3 py-1 text-sm"
          >
            Exportar CSV (formato RUD)
          </button>
        }
      >
        {items.length === 0 && <p className="text-sm text-tinta-suave">Aún no hay hogares.</p>}
        <ul className="flex flex-col divide-y divide-linea">
          {items.map((h) => (
            <li key={h.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <span className="font-mono font-semibold">{h.code}</span>
              <span>
                {h.members_count} {h.members_count === 1 ? "persona" : "personas"}
                {h.pets_count > 0 && ` · ${h.pets_count} mascotas`}
              </span>
              <span className="text-tinta-suave">{h.barrio ?? h.manzana_id ?? "sin predio"}</span>
              {h.vulnerability_score > 0 && (
                <span className="rounded bg-amber-100 px-1.5 text-xs text-amber-900">
                  Prioridad {h.vulnerability_score}:{" "}
                  {(Object.keys(VULN_LABEL) as (keyof typeof VULN_LABEL)[])
                    .filter((k) => h.vulnerability[k])
                    .map((k) => VULN_LABEL[k])
                    .join(", ")}
                </span>
              )}
              <span className="ml-auto flex items-center gap-2 text-xs text-tinta-suave">
                {h.aid_count} ayudas · {RUD_LABEL[h.rud_status]}
                {h.rud_status === "pendiente" && (
                  <button
                    type="button"
                    onClick={() => inscribir(h)}
                    className="rounded border border-linea px-2 py-0.5 text-tinta"
                  >
                    Inscribir en RUD
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- ayudas

function Ayudas({ tick }: { tick: number }) {
  const [document, setDocument] = useState("");
  const [aidType, setAidType] = useState<AidType>("mercado");
  const [fund, setFund] = useState("Fondo Municipal de Gestión del Riesgo");
  const [justification, setJustification] = useState("");
  const [needsJustification, setNeedsJustification] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);
  const [items, setItems] = useState<AidOut[]>([]);

  const load = useCallback(
    () => api.GET("/api/v1/recovery/aid").then(({ data }) => data && setItems(data.items)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    const { data, error, response } = await api.POST("/api/v1/recovery/aid", {
      body: {
        document,
        aid_type: aidType,
        source_fund: fund,
        justification: justification.trim() || null,
      },
    });
    if (response.status === 409) {
      setNeedsJustification(true);
      setMsg({ tone: "warn", text: errorText(error, "Ayuda duplicada") });
      return;
    }
    if (error || !data) {
      setMsg({ tone: "error", text: errorText(error, "No se pudo registrar la ayuda") });
      return;
    }
    setDocument("");
    setJustification("");
    setNeedsJustification(false);
    setMsg(
      data.is_duplicate
        ? {
            tone: "warn",
            text: `Ayuda repetida entregada al hogar ${data.household_code} con justificación (queda marcada).`,
          }
        : {
            tone: "ok",
            text: `${AID_LABEL[data.aid_type]} entregada al hogar ${data.household_code}.`,
          },
    );
    await load();
  }

  const duplicates = items.filter((a) => a.is_duplicate).length;

  return (
    <div className="flex flex-col gap-4">
      <Card title="Entregar ayuda">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Documento del jefe de hogar
              <input
                className={input}
                value={document}
                onChange={(e) => {
                  setDocument(e.target.value);
                  setNeedsJustification(false);
                }}
                autoComplete="off"
                inputMode="numeric"
                required
                minLength={5}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Tipo de ayuda
              <select
                className={input}
                value={aidType}
                onChange={(e) => {
                  setAidType(e.target.value as AidType);
                  setNeedsJustification(false);
                }}
              >
                {(Object.keys(AID_LABEL) as AidType[]).map((t) => (
                  <option key={t} value={t}>
                    {AID_LABEL[t]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Fondo
              <input className={input} value={fund} onChange={(e) => setFund(e.target.value)} />
            </label>
          </div>
          {needsJustification && (
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Justificación para entregar de nuevo
              <input
                className={input}
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="Ej.: hogar con 6 integrantes, el primer mercado no alcanzó"
              />
            </label>
          )}
          <div>
            <button
              type="submit"
              className={button}
              disabled={document.trim().length < 5 || (needsJustification && !justification.trim())}
            >
              {needsJustification ? "Entregar con justificación" : "Registrar entrega"}
            </button>
          </div>
          {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
        </form>
      </Card>

      <Card
        title={`Entregas (${formatInt(items.length)})`}
        extra={
          duplicates > 0 ? (
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-900">
              {duplicates} repetidas con justificación
            </span>
          ) : undefined
        }
      >
        {items.length === 0 && <p className="text-sm text-tinta-suave">Aún no hay entregas.</p>}
        <ul className="flex flex-col divide-y divide-linea">
          {items.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
              <span className="font-mono font-semibold">{a.household_code}</span>
              <span>{AID_LABEL[a.aid_type]}</span>
              {a.is_duplicate && (
                <span
                  className="rounded bg-amber-100 px-1.5 text-xs text-amber-900"
                  title={a.justification ?? ""}
                >
                  Repetida · {a.justification}
                </span>
              )}
              <span className="ml-auto text-xs text-tinta-suave">
                {a.source_fund} · {formatDateTime(a.at)}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

// --------------------------------------------------------------------------- albergues

function Albergues({ tick }: { tick: number }) {
  const [items, setItems] = useState<ShelterOut[]>([]);
  const [edits, setEdits] = useState<Record<string, { people: number; pets: number }>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () => api.GET("/api/v1/recovery/shelters").then(({ data }) => data && setItems(data.items)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function save(s: ShelterOut) {
    const edit = edits[s.id];
    if (!edit) return;
    setError(null);
    const { error: err } = await api.PATCH("/api/v1/recovery/shelters/{shelter_id}", {
      params: { path: { shelter_id: s.id } },
      body: edit,
    });
    if (err) {
      setError(errorText(err, "No se pudo actualizar el albergue"));
      return;
    }
    setEdits((prev) => {
      const next = { ...prev };
      delete next[s.id];
      return next;
    });
    await load();
  }

  return (
    <Card title="Albergues temporales">
      <ul className="flex flex-col divide-y divide-linea">
        {items.map((s) => {
          const edit = edits[s.id] ?? { people: s.people, pets: s.pets };
          const pct = s.capacity ? Math.round((s.people / s.capacity) * 100) : 0;
          return (
            <li key={s.id} className="flex flex-col gap-2 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{s.name}</span>
                <span className="text-tinta-suave">{s.barrio}</span>
                {DEMO_MODE && s.source === "SIMULADO" && <EtiquetaSimulado />}
                <span className="ml-auto text-xs text-tinta-suave">
                  {formatInt(s.people)} / {formatInt(s.capacity)} personas · {formatInt(s.pets)}{" "}
                  mascotas
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-linea">
                <div
                  className="h-full"
                  style={{
                    width: `${pct}%`,
                    background: pct >= 90 ? "#d21f2b" : pct >= 70 ? "#e8a92a" : "#2f7d55",
                  }}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <label className="flex items-center gap-1">
                  Personas
                  <input
                    type="number"
                    min={0}
                    max={s.capacity}
                    className={`${input} w-24`}
                    value={edit.people}
                    onChange={(e) =>
                      setEdits({ ...edits, [s.id]: { ...edit, people: Number(e.target.value) } })
                    }
                  />
                </label>
                <label className="flex items-center gap-1">
                  Mascotas
                  <input
                    type="number"
                    min={0}
                    className={`${input} w-20`}
                    value={edit.pets}
                    onChange={(e) =>
                      setEdits({ ...edits, [s.id]: { ...edit, pets: Number(e.target.value) } })
                    }
                  />
                </label>
                <button
                  type="button"
                  disabled={!edits[s.id]}
                  onClick={() => save(s)}
                  className="rounded border border-linea px-3 py-1 disabled:opacity-40"
                >
                  Actualizar ocupación
                </button>
                <span className="text-tinta-suave">Actualizado {formatTime(s.updated_at)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      {error && <Notice tone="error">{error}</Notice>}
    </Card>
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
