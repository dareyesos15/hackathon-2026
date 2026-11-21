"use client";
/**
 * Censo único de damnificados con los campos del RUD (UNGRD). Un hogar por documento del jefe de
 * hogar (HMAC con sal en la API); la planilla de censo no se registra dos veces.
 *
 * Ley 1581: de los integrantes solo se registran conteos por edad, mujeres y pertenencia étnica;
 * nombres, documentos y fechas de nacimiento quedan en la planilla en papel. La vulnerabilidad
 * (dato sensible) vive en una tabla separada visible solo para PMU/COE. El documento se borra
 * del formulario al enviar y nunca se guarda en el navegador.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { API_BASE, api } from "@/lib/api/client";
import { formatInt } from "@/lib/format";
import {
  HOUSING_STATUS_LABEL,
  LOSS_LABEL,
  RUD_LABEL,
  SITUATION_LABEL,
  TENURE_LABEL,
  errorText,
  type HouseholdLoss,
  type HouseholdOut,
  type HousingStatus,
  type ManzanaRef,
  type Tenure,
} from "@/lib/recovery";
import { getSession } from "@/lib/session";
import { Casillas, Numero, Opciones, Seccion } from "./FormatoRevision";
import { Card, EMPTY_PROPERTY, Notice, PropertyFields, button, input, propertyBody } from "./ui";

type Msg = { tone: "ok" | "warn" | "error"; text: string } | null;

export function Censo({ manzanas, tick }: { manzanas: ManzanaRef[]; tick: number }) {
  const [formNumber, setFormNumber] = useState("");
  const [document, setDocument] = useState("");
  const [property, setProperty] = useState(EMPTY_PROPERTY);
  const [tenure, setTenure] = useState<Tenure | null>(null);
  const [status, setStatus] = useState<HousingStatus | "auto">("auto");
  const [ages, setAges] = useState({ a0: 0, a6: 0, a18: 1, a60: 0 });
  const [women, setWomen] = useState(0);
  const [ethnic, setEthnic] = useState(0);
  const [pets, setPets] = useState(0);
  const [disability, setDisability] = useState(false);
  const [pregnancy, setPregnancy] = useState(false);
  const [losses, setLosses] = useState<HouseholdLoss[]>([]);
  const [msg, setMsg] = useState<Msg>(null);
  const [items, setItems] = useState<HouseholdOut[]>([]);

  const members = ages.a0 + ages.a6 + ages.a18 + ages.a60;

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
        census_form_number: formNumber.trim() || null,
        members_count: members,
        pets_count: pets,
        rud_status: "pendiente",
        tenure,
        housing_status: status === "auto" ? null : status,
        age_0_5: ages.a0,
        age_6_17: ages.a6,
        age_18_59: ages.a18,
        age_60_plus: ages.a60,
        female_members: women,
        ethnic_members: ethnic,
        losses,
        vulnerability: {
          children: ages.a0 + ages.a6 > 0,
          elderly: ages.a60 > 0,
          disability,
          pregnancy,
        },
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
    setFormNumber("");
    setProperty(EMPTY_PROPERTY);
    setTenure(null);
    setStatus("auto");
    setAges({ a0: 0, a6: 0, a18: 1, a60: 0 });
    setWomen(0);
    setEthnic(0);
    setPets(0);
    setDisability(false);
    setPregnancy(false);
    setLosses([]);
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

  const problem =
    members < 1
      ? "El hogar debe tener al menos un integrante."
      : women > members || ethnic > members
        ? "Mujeres o pertenencia étnica superan a los integrantes."
        : null;

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Registrar hogar damnificado"
        extra={
          <span className="text-xs text-tinta-suave">
            Campos del Registro Único de Damnificados (RUD · UNGRD)
          </span>
        }
      >
        <form onSubmit={submit} className="flex flex-col gap-3">
          <p className="text-xs text-tinta-suave">
            El documento del jefe de hogar solo evita registros duplicados: Dacora guarda una huella
            cifrada (HMAC con sal), nunca el número. Nombres, documentos y fechas de nacimiento de
            los integrantes <strong>quedan en la planilla en papel</strong> (Ley 1581). Si el hogar
            ya llegó por una revisión a predio, aquí solo se completa.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              N.º de la planilla de censo
              <input
                className={input}
                value={formNumber}
                onChange={(e) => setFormNumber(e.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
              />
            </label>
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
          </div>

          <Seccion n="1" title="Ubicación y vivienda">
            <PropertyFields manzanas={manzanas} value={property} onChange={setProperty} optional />
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1 text-xs text-tinta-suave">
                Régimen de tenencia
                <Opciones
                  name="tenencia"
                  options={TENURE_LABEL}
                  value={tenure}
                  onChange={setTenure}
                />
              </div>
              <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                Estado de la vivienda
                <select
                  className={input}
                  value={status}
                  onChange={(e) => setStatus(e.target.value as HousingStatus | "auto")}
                >
                  <option value="auto">Según el semáforo del predio (automático)</option>
                  {(Object.keys(HOUSING_STATUS_LABEL) as HousingStatus[]).map((k) => (
                    <option key={k} value={k}>
                      {HOUSING_STATUS_LABEL[k]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </Seccion>

          <Seccion n="2" title={`Integrantes del hogar (${formatInt(members)})`}>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Numero
                label="De 0 a 5 años"
                value={ages.a0}
                onChange={(v) => setAges({ ...ages, a0: v })}
              />
              <Numero
                label="De 6 a 17 años"
                value={ages.a6}
                onChange={(v) => setAges({ ...ages, a6: v })}
              />
              <Numero
                label="De 18 a 59 años"
                value={ages.a18}
                onChange={(v) => setAges({ ...ages, a18: v })}
              />
              <Numero
                label="60 años o más"
                value={ages.a60}
                onChange={(v) => setAges({ ...ages, a60: v })}
              />
              <Numero label="Mujeres" value={women} onChange={setWomen} />
              <Numero label="Pertenencia étnica" value={ethnic} onChange={setEthnic} />
              <Numero label="Mascotas" value={pets} onChange={setPets} />
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
              <span className="text-xs text-tinta-suave">
                Prioridad (dato sensible, acceso restringido): niñez y adulto mayor se marcan solos
                con las edades.
              </span>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={disability}
                  onChange={(e) => setDisability(e.target.checked)}
                />
                Persona con discapacidad
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={pregnancy}
                  onChange={(e) => setPregnancy(e.target.checked)}
                />
                Gestante o lactante
              </label>
            </div>
          </Seccion>

          <Seccion n="3" title="Pérdidas">
            <Casillas options={LOSS_LABEL} value={losses} onChange={setLosses} />
          </Seccion>

          {problem && <Notice tone="error">{problem}</Notice>}
          <div>
            <button
              type="submit"
              className={button}
              disabled={document.trim().length < 5 || Boolean(problem)}
            >
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
          {items.map((h) => {
            const sit = h.situation ? SITUATION_LABEL[h.situation] : null;
            return (
              <li key={h.id} className="flex flex-col gap-1 py-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono font-semibold">{h.code}</span>
                  {h.census_form_number && (
                    <span className="text-xs text-tinta-suave">
                      planilla N.º {h.census_form_number}
                    </span>
                  )}
                  <span>
                    {h.members_count} {h.members_count === 1 ? "persona" : "personas"}
                    {h.pets_count > 0 && ` · ${h.pets_count} mascotas`}
                  </span>
                  <span className="text-tinta-suave">
                    {h.barrio ?? h.manzana_id ?? "sin predio"}
                  </span>
                  {sit && (
                    <span className={`rounded px-1.5 text-xs font-semibold ${sit.cls}`}>
                      {sit.label}
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
                </div>
                <div className="flex flex-wrap gap-x-3 text-xs text-tinta-suave">
                  {h.tenure && <span>{TENURE_LABEL[h.tenure]}</span>}
                  {h.housing_status && (
                    <span>Vivienda {HOUSING_STATUS_LABEL[h.housing_status].toLowerCase()}</span>
                  )}
                  {h.age_0_5 + h.age_6_17 + h.age_18_59 + h.age_60_plus > 0 && (
                    <span>
                      Edades: {h.age_0_5} de 0–5 · {h.age_6_17} de 6–17 · {h.age_18_59} de 18–59 ·{" "}
                      {h.age_60_plus} de 60+
                    </span>
                  )}
                  {h.vulnerability_score > 0 && (
                    <span className="rounded bg-amber-100 px-1.5 text-amber-900">
                      Prioridad {h.vulnerability_score}
                    </span>
                  )}
                  {(h.losses ?? []).length > 0 && (
                    <span>
                      Pérdidas:{" "}
                      {(h.losses ?? []).map((l) => LOSS_LABEL[l].toLowerCase()).join(", ")}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
