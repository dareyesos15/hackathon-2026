"use client";
/**
 * Revisión a predio: versión digital del formato GUE-RPD-FR-02 v4 de la Alcaldía de Manizales,
 * con las mismas secciones del papel (1 a 7, fecha y hora, revisor).
 *
 * Un solo envío alimenta habitabilidad (semáforo NSR-10), censo único (hogar ligado por HMAC) y
 * derivaciones a entidades. Ley 1581: nombres, teléfonos, cédulas y fechas de nacimiento quedan
 * solo en el papel; el documento del encuestado viaja a la API (que guarda una huella con sal) y
 * se borra del formulario al enviar. Nada se guarda en el navegador.
 */
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt } from "@/lib/format";
import {
  AFFECTATION_LABEL,
  CAUSE_LABEL,
  COLOR_DAMAGE,
  COLOR_LABEL,
  DAMAGE_LABEL,
  ENTITY_LABEL,
  EVENT_STATUS_LABEL,
  EVENT_TYPE_LABEL,
  INFRA_LABEL,
  RELATION_LABEL,
  errorText,
  reviewInconsistency,
  suggestSemaphore,
  type Affectation,
  type AffectedInfrastructure,
  type DamageLevel,
  type EventStatus,
  type EventType,
  type InspectionColor,
  type ManzanaRef,
  type PropertyReviewOut,
  type ReferralEntity,
  type ReferralList,
  type RespondentRelation,
  type StructuralCause,
} from "@/lib/recovery";
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

/** Sección numerada como en el formato en papel. */
export function Seccion({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-2 rounded-md border border-linea p-3">
      <legend className="px-1 text-sm font-semibold">
        <span className="mr-1 text-tinta-suave">{n}.</span>
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

export function Casillas<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Record<T, string>;
  value: T[];
  onChange: (v: T[]) => void;
}) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {(Object.keys(options) as T[]).map((k) => (
        <label key={k} className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={value.includes(k)}
            onChange={(e) =>
              onChange(e.target.checked ? [...value, k] : value.filter((x) => x !== k))
            }
          />
          {options[k]}
        </label>
      ))}
    </div>
  );
}

export function Opciones<T extends string>({
  name,
  options,
  value,
  onChange,
}: {
  name: string;
  options: Record<T, string>;
  value: T | null;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {(Object.keys(options) as T[]).map((k) => (
        <label key={k} className="flex items-center gap-1.5">
          <input type="radio" name={name} checked={value === k} onChange={() => onChange(k)} />
          {options[k]}
        </label>
      ))}
    </div>
  );
}

export function Numero({
  label,
  value,
  onChange,
  max = 30,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  max?: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-tinta-suave">
      {label}
      <input
        type="number"
        min={0}
        max={max}
        className={input}
        value={value}
        onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
      />
    </label>
  );
}

function localNow(): string {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

const EMPTY_AREAS: Record<AffectedInfrastructure, string> = {
  vivienda: "",
  vial: "",
  educativa: "",
  comunitaria: "",
};

export function FormatoRevision({
  manzanas,
  onSaved,
}: {
  manzanas: ManzanaRef[];
  onSaved: () => void;
}) {
  const [formNumber, setFormNumber] = useState("");
  const [reviewedAt, setReviewedAt] = useState(localNow);
  const [property, setProperty] = useState(EMPTY_PROPERTY);
  const [document, setDocument] = useState("");
  const [relation, setRelation] = useState<RespondentRelation | null>(null);
  const [ownerDocument, setOwnerDocument] = useState("");
  const [residents, setResidents] = useState(0);
  const [minors, setMinors] = useState(0);
  const [elderly, setElderly] = useState(0);
  const [disability, setDisability] = useState(0);
  const [pregnancy, setPregnancy] = useState(0);
  const [pets, setPets] = useState(0);
  const [eventStatus, setEventStatus] = useState<EventStatus>("sucedido");
  const [eventTypes, setEventTypes] = useState<EventType[]>(["sismo"]);
  const [eventOther, setEventOther] = useState("");
  const [causes, setCauses] = useState<StructuralCause[]>(["evento_natural"]);
  const [affectation, setAffectation] = useState<Affectation>("parcial");
  const [areas, setAreas] = useState(EMPTY_AREAS);
  const [belongings, setBelongings] = useState("");
  const [referrals, setReferrals] = useState<ReferralEntity[]>([]);
  const [referralOther, setReferralOther] = useState("");
  const [evacuation, setEvacuation] = useState(false);
  const [override, setOverride] = useState<{ color: InspectionColor; damage: DamageLevel } | null>(
    null,
  );
  const [agency, setAgency] = useState("Cuerpo Oficial de Bomberos");
  const [signed, setSigned] = useState(false);
  const [notes, setNotes] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<PropertyReviewOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [suggestedColor, suggestedDamage] = suggestSemaphore(affectation, evacuation);
  const color = override?.color ?? suggestedColor;
  const damage = override?.damage ?? suggestedDamage;
  const problem =
    reviewInconsistency(color, affectation, evacuation) ??
    (residents > 0 && minors + elderly > residents
      ? "Hay más menores y mayores que residentes."
      : null);

  function pickColor(c: InspectionColor) {
    const d = COLOR_DAMAGE[c].includes(damage) ? damage : COLOR_DAMAGE[c][0];
    setOverride(c === suggestedColor && d === suggestedDamage ? null : { color: c, damage: d });
  }

  function reset() {
    setFormNumber("");
    setReviewedAt(localNow());
    setProperty(EMPTY_PROPERTY);
    setRelation(null);
    setResidents(0);
    setMinors(0);
    setElderly(0);
    setDisability(0);
    setPregnancy(0);
    setPets(0);
    setEventTypes(["sismo"]);
    setEventOther("");
    setAffectation("parcial");
    setAreas(EMPTY_AREAS);
    setBelongings("");
    setReferrals([]);
    setReferralOther("");
    setEvacuation(false);
    setOverride(null);
    setSigned(false);
    setNotes("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSending(true);
    const areaBody = Object.fromEntries(
      Object.entries(areas)
        .filter(([, v]) => v.trim() !== "" && Number(v) > 0)
        .map(([k, v]) => [k, Number(v)]),
    );
    const { data, error: err } = await api.POST("/api/v1/recovery/reviews", {
      body: {
        ...propertyBody(property),
        form_number: formNumber.trim() || null,
        reviewed_at: reviewedAt ? new Date(reviewedAt).toISOString() : null,
        respondent_document: document.trim() || null,
        respondent_relation: relation,
        owner_document: relation === "arrendatario" ? ownerDocument.trim() || null : null,
        residents,
        minors,
        elderly,
        disability,
        pregnancy,
        pets,
        event_status: eventStatus,
        event_types: eventTypes,
        event_other: eventTypes.includes("otro") ? eventOther.trim() || null : null,
        structural_causes: causes,
        affectation,
        affected_areas_m2: areaBody,
        belongings_loss: belongings.trim() || null,
        referrals,
        referral_other: referrals.includes("otro") ? referralOther.trim() || null : null,
        evacuation_recommended: evacuation,
        color,
        damage_level: damage,
        notes: notes.trim() || null,
        reviewer_agency: agency,
        notified_signed: signed,
      },
    });
    // Los documentos nunca quedan en pantalla después de enviar (Ley 1581).
    setDocument("");
    setOwnerDocument("");
    setSending(false);
    if (err || !data) {
      setError(errorText(err, "No se pudo registrar la revisión"));
      return;
    }
    setResult(data);
    reset();
    onSaved();
  }

  return (
    <Card
      title="Revisión a predio"
      extra={
        <span className="text-xs text-tinta-suave">
          Formato GUE-RPD-FR-02 · versión 4 · Alcaldía de Manizales
        </span>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-3">
        <p className="text-xs text-tinta-suave">
          Transcriba el formato en papel o llénelo en terreno. Nombres, teléfonos, cédulas y fechas
          de nacimiento <strong>quedan solo en el papel</strong> (Ley 1581): aquí se registran
          conteos y una huella cifrada del documento para no duplicar el hogar en el censo.
        </p>
        <div className="grid gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-tinta-suave">
            N.º del formato (impreso en rojo)
            <input
              className={input}
              value={formNumber}
              onChange={(e) => setFormNumber(e.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
              placeholder="21451"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-tinta-suave">
            Fecha y hora de la revisión
            <input
              type="datetime-local"
              className={input}
              value={reviewedAt}
              onChange={(e) => setReviewedAt(e.target.value)}
            />
          </label>
        </div>

        <Seccion n="1" title="Dirección del predio y barrio">
          <PropertyFields manzanas={manzanas} value={property} onChange={setProperty} />
        </Seccion>

        <Seccion n="2" title="Encuestado">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Documento del encuestado (solo para ligar el hogar en el censo)
              <input
                className={input}
                value={document}
                onChange={(e) => setDocument(e.target.value)}
                autoComplete="off"
                inputMode="numeric"
                minLength={5}
              />
            </label>
            <div className="flex flex-col gap-1 text-xs text-tinta-suave">
              Calidad frente al predio
              <Opciones
                name="relacion"
                options={RELATION_LABEL}
                value={relation}
                onChange={setRelation}
              />
            </div>
          </div>
          {relation === "arrendatario" && (
            <label className="flex flex-col gap-1 text-xs text-tinta-suave sm:w-1/2">
              Documento del propietario (se guarda solo como huella cifrada)
              <input
                className={input}
                value={ownerDocument}
                onChange={(e) => setOwnerDocument(e.target.value)}
                autoComplete="off"
                inputMode="numeric"
                minLength={5}
              />
            </label>
          )}
        </Seccion>

        <Seccion n="3" title="Residentes">
          <p className="text-xs text-tinta-suave">
            Cuente las filas de la sección 3 del papel; las edades salen de las fechas de
            nacimiento. Los menores, mayores, personas con discapacidad y gestantes marcan la
            prioridad del hogar.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
            <Numero label="Residentes" value={residents} onChange={setResidents} />
            <Numero label="Menores de 18" value={minors} onChange={setMinors} />
            <Numero label="Mayores de 60" value={elderly} onChange={setElderly} />
            <Numero label="Con discapacidad" value={disability} onChange={setDisability} />
            <Numero label="Gestantes" value={pregnancy} onChange={setPregnancy} />
            <Numero label="Mascotas" value={pets} onChange={setPets} />
          </div>
        </Seccion>

        <Seccion n="4" title="Evento">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="flex flex-col gap-1 text-xs text-tinta-suave">
              Evento
              <Opciones
                name="estado"
                options={EVENT_STATUS_LABEL}
                value={eventStatus}
                onChange={setEventStatus}
              />
            </div>
            <div className="flex flex-col gap-1 text-xs text-tinta-suave">
              Tipo
              <Casillas options={EVENT_TYPE_LABEL} value={eventTypes} onChange={setEventTypes} />
              {eventTypes.includes("otro") && (
                <input
                  className={input}
                  value={eventOther}
                  onChange={(e) => setEventOther(e.target.value)}
                  placeholder="¿Cuál?"
                />
              )}
            </div>
            <div className="flex flex-col gap-1 text-xs text-tinta-suave">
              Deterioro estructural: posible causa
              <Casillas options={CAUSE_LABEL} value={causes} onChange={setCauses} />
            </div>
          </div>
        </Seccion>

        <Seccion n="5" title="Afectación">
          <Opciones
            name="afectacion"
            options={AFFECTATION_LABEL}
            value={affectation}
            onChange={(v) => {
              setAffectation(v);
              setOverride(null);
            }}
          />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(Object.keys(INFRA_LABEL) as AffectedInfrastructure[]).map((k) => (
              <label key={k} className="flex flex-col gap-1 text-xs text-tinta-suave">
                {INFRA_LABEL[k]} (m²)
                <input
                  type="number"
                  min={0}
                  step="0.1"
                  className={input}
                  value={areas[k]}
                  onChange={(e) => setAreas({ ...areas, [k]: e.target.value })}
                />
              </label>
            ))}
          </div>
          <label className="flex flex-col gap-1 text-xs text-tinta-suave">
            Pérdida de bienes muebles y enseres: ¿cuál? (sin nombres ni teléfonos)
            <input
              className={input}
              value={belongings}
              onChange={(e) => setBelongings(e.target.value)}
            />
          </label>
        </Seccion>

        <Seccion n="6" title="Requiere visita">
          <Casillas options={ENTITY_LABEL} value={referrals} onChange={setReferrals} />
          {referrals.includes("otro") && (
            <input
              className={input}
              value={referralOther}
              onChange={(e) => setReferralOther(e.target.value)}
              placeholder="¿Qué entidad?"
            />
          )}
        </Seccion>

        <Seccion n="7" title="Se recomienda evacuación">
          <Opciones
            name="evacuacion"
            options={{ si: "Sí", no: "No" }}
            value={evacuation ? "si" : "no"}
            onChange={(v) => {
              setEvacuation(v === "si");
              setOverride(null);
            }}
          />
          {evacuation && (
            <Notice tone="warn">
              Indique a la familia llamar a la Cruz Roja Colombiana Seccional Caldas (886 6300) para
              el auxilio de arrendamiento o la ayuda humanitaria, con fotocopia de esta revisión y
              de la cédula del titular.
            </Notice>
          )}
        </Seccion>

        <Seccion n="NSR-10" title="Semáforo de habitabilidad">
          <p className="text-xs text-tinta-suave">
            Sugerido por la afectación y la evacuación:{" "}
            <strong>
              {COLOR_LABEL[suggestedColor]} · {DAMAGE_LABEL[suggestedDamage]}
            </strong>
            . Ajústelo si la inspección lo justifica.
          </p>
          <div className="flex flex-wrap gap-2">
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
          </div>
          <label className="flex flex-col gap-1 text-xs text-tinta-suave sm:w-1/2">
            Nivel de daño (NSR-10)
            <select
              className={input}
              value={damage}
              onChange={(e) => setOverride({ color, damage: e.target.value as DamageLevel })}
            >
              {COLOR_DAMAGE[color].map((d) => (
                <option key={d} value={d}>
                  {DAMAGE_LABEL[d]}
                </option>
              ))}
            </select>
          </label>
        </Seccion>

        <div className="grid gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs text-tinta-suave">
            Entidad que revisa
            <input className={input} value={agency} onChange={(e) => setAgency(e.target.value)} />
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" checked={signed} onChange={(e) => setSigned(e.target.checked)} />
            La persona notificada firmó el formato
          </label>
          <label className="flex flex-col gap-1 text-xs text-tinta-suave">
            Observaciones (sin nombres ni teléfonos)
            <input className={input} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>

        {problem && <Notice tone="error">{problem}</Notice>}
        <div>
          <button
            type="submit"
            className={button}
            disabled={sending || Boolean(problem) || eventTypes.length === 0}
          >
            {sending ? "Registrando…" : "Registrar revisión"}
          </button>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        {result && (
          <div className="flex flex-col gap-2 rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            <p className="flex flex-wrap items-center gap-2 font-semibold">
              <Dot color={result.color} />
              Revisión {result.form_number ? `N.º ${result.form_number} ` : ""}registrada:{" "}
              {COLOR_LABEL[result.color]} · {DAMAGE_LABEL[result.damage_level]}
            </p>
            <ul className="list-disc pl-5">
              {result.next_steps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        )}
      </form>
    </Card>
  );
}

// --------------------------------------------------------------------------- derivaciones

export function Derivaciones({ tick }: { tick: number }) {
  const [data, setData] = useState<ReferralList | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () => api.GET("/api/v1/recovery/referrals").then(({ data: d }) => d && setData(d)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load, tick]);

  async function mark(reviewId: string, entity: ReferralEntity) {
    setError(null);
    const { error: err } = await api.PATCH(
      "/api/v1/recovery/reviews/{review_id}/referrals/{entity}",
      { params: { path: { review_id: reviewId, entity } }, body: { done: true } },
    );
    if (err) {
      setError(errorText(err, "No se pudo marcar la visita"));
      return;
    }
    await load();
  }

  const pending = data?.pending ?? [];
  return (
    <Card title={`Visitas de entidades pendientes (${formatInt(pending.length)})`}>
      <p className="text-xs text-tinta-suave">
        Sección 6 del formato. Primero los predios con evacuación recomendada. Cada entidad marca su
        visita al hacerla.
      </p>
      {data && data.summary.length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs">
          {data.summary.map((s) => (
            <span key={s.entity} className="rounded border border-linea px-2 py-0.5">
              {ENTITY_LABEL[s.entity]}: <strong>{s.pending}</strong> pendientes · {s.done} atendidas
            </span>
          ))}
        </div>
      )}
      {pending.length === 0 ? (
        <p className="text-sm text-tinta-suave">No hay visitas pendientes.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-linea">
          {pending.map((r) => (
            <li
              key={`${r.review_id}-${r.entity}`}
              className="flex flex-wrap items-center gap-2 py-2 text-sm"
            >
              <span className="font-semibold">{ENTITY_LABEL[r.entity]}</span>
              <span>{r.property_id}</span>
              <span className="text-tinta-suave">{r.barrio ?? ""}</span>
              {r.evacuation_recommended && (
                <span className="rounded bg-senal-fondo px-1.5 text-xs font-semibold text-senal">
                  Evacuación recomendada
                </span>
              )}
              <span className="text-xs text-tinta-suave">
                Afectación {AFFECTATION_LABEL[r.affectation].toLowerCase()}
                {r.form_number ? ` · formato N.º ${r.form_number}` : ""} ·{" "}
                {formatDateTime(r.reviewed_at)}
              </span>
              <button
                type="button"
                onClick={() => mark(r.review_id, r.entity)}
                className="ml-auto rounded border border-linea px-2 py-0.5 text-xs"
              >
                Marcar visita hecha
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <Notice tone="error">{error}</Notice>}
    </Card>
  );
}

/** Detalle de los formatos de un predio (dentro del historial de visitas). */
export function DetalleRevisiones({ propertyId }: { propertyId: string }) {
  const [items, setItems] = useState<PropertyReviewOut[] | null>(null);
  useEffect(() => {
    api
      .GET("/api/v1/recovery/reviews", { params: { query: { property_id: propertyId } } })
      .then(({ data }) => setItems(data ?? []));
  }, [propertyId]);
  if (!items || items.length === 0) return null;
  return (
    <ul className="mt-2 ml-5 flex flex-col gap-1 text-xs text-tinta-suave">
      {items.map((r) => (
        <li key={r.id}>
          <span className="font-semibold text-tinta">
            Formato {r.form_number ? `N.º ${r.form_number}` : "sin número"}
          </span>{" "}
          · {formatDateTime(r.reviewed_at)} · {r.reviewer_agency} · evento{" "}
          {r.event_types.map((t) => EVENT_TYPE_LABEL[t].toLowerCase()).join(", ")} (
          {EVENT_STATUS_LABEL[r.event_status].toLowerCase()}) · afectación{" "}
          {AFFECTATION_LABEL[r.affectation].toLowerCase()} · {formatInt(r.residents)} residentes
          {r.evacuation_recommended ? " · evacuación recomendada" : ""}
          {r.referrals.length > 0 &&
            ` · derivado a ${r.referrals
              .map((e) => `${ENTITY_LABEL[e]}${r.referrals_done.includes(e) ? " (atendida)" : ""}`)
              .join(", ")}`}
          {r.household_code ? ` · hogar ${r.household_code}` : ""}
        </li>
      ))}
    </ul>
  );
}
