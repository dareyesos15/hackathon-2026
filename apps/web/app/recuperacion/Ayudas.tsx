"use client";
/**
 * Ayudas: cada entrega es un acta de entrega de ayuda humanitaria (N.º, entidad, cantidad, firma).
 * - El acta no se registra dos veces; la misma ayuda al mismo hogar en su periodo se bloquea salvo
 *   justificación (evita doble beneficio).
 * - Subsidio de arriendo: valor mensual y meses.
 * - Cupo en albergue: el hogar entra al albergue elegido y su ocupación sube sola; "Registrar
 *   salida" la baja.
 * Ley 1581: el documento solo viaja a la API (HMAC) y se borra del formulario al enviar.
 */
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api } from "@/lib/api/client";
import { formatCop, formatDateTime, formatInt } from "@/lib/format";
import { AID_LABEL, errorText, type AidOut, type AidType, type ShelterOut } from "@/lib/recovery";
import { Card, Notice, button, input } from "./ui";

type Msg = { tone: "ok" | "warn" | "error"; text: string } | null;

function detalle(a: AidOut): string {
  if (a.aid_type === "subsidio_arriendo" && a.amount_cop)
    return `${formatCop(a.amount_cop)} mensuales × ${a.months ?? 1} ${a.months === 1 ? "mes" : "meses"}`;
  if (a.aid_type === "albergue")
    return `${a.shelter_name ?? "albergue"} · ${a.members} personas${a.ended_at ? ` · salió ${formatDateTime(a.ended_at)}` : " · alojado"}`;
  return `${formatInt(a.quantity)} ${a.quantity === 1 ? "unidad" : "unidades"}`;
}

export function Ayudas({ tick }: { tick: number }) {
  const [act, setAct] = useState("");
  const [document, setDocument] = useState("");
  const [aidType, setAidType] = useState<AidType>("mercado");
  const [quantity, setQuantity] = useState(1);
  const [deliveredBy, setDeliveredBy] = useState("Cruz Roja Colombiana Seccional Caldas");
  const [fund, setFund] = useState("Fondo Municipal de Gestión del Riesgo");
  const [amount, setAmount] = useState("");
  const [months, setMonths] = useState(3);
  const [shelterId, setShelterId] = useState("");
  const [signed, setSigned] = useState(true);
  const [justification, setJustification] = useState("");
  const [needsJustification, setNeedsJustification] = useState(false);
  const [msg, setMsg] = useState<Msg>(null);
  const [items, setItems] = useState<AidOut[]>([]);
  const [shelters, setShelters] = useState<ShelterOut[]>([]);

  const load = useCallback(
    () =>
      Promise.all([api.GET("/api/v1/recovery/aid"), api.GET("/api/v1/recovery/shelters")]).then(
        ([aid, sh]) => {
          if (aid.data) setItems(aid.data.items);
          if (sh.data) setShelters(sh.data.items);
        },
      ),
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
        act_number: act.trim() || null,
        delivered_by: deliveredBy.trim() || null,
        quantity,
        amount_cop: aidType === "subsidio_arriendo" ? Number(amount) || null : null,
        months: aidType === "subsidio_arriendo" ? months : null,
        shelter_id: aidType === "albergue" ? shelterId || null : null,
        signed,
      },
    });
    if (
      response.status === 409 &&
      (error as { code?: string } | undefined)?.code === "aid_duplicate"
    ) {
      setNeedsJustification(true);
      setMsg({ tone: "warn", text: errorText(error, "Ayuda duplicada") });
      return;
    }
    if (error || !data) {
      setMsg({ tone: "error", text: errorText(error, "No se pudo registrar la entrega") });
      return;
    }
    setDocument("");
    setJustification("");
    setNeedsJustification(false);
    setAct("");
    setMsg(
      data.is_duplicate
        ? {
            tone: "warn",
            text: `Ayuda repetida entregada al hogar ${data.household_code} con justificación (queda marcada).`,
          }
        : {
            tone: "ok",
            text: `${AID_LABEL[data.aid_type]} entregada al hogar ${data.household_code}: ${detalle(data)}.`,
          },
    );
    await load();
  }

  async function salida(a: AidOut) {
    const { error } = await api.POST("/api/v1/recovery/aid/{aid_id}/end", {
      params: { path: { aid_id: a.id } },
    });
    setMsg(
      error
        ? { tone: "error", text: errorText(error, "No se pudo registrar la salida") }
        : { tone: "ok", text: `Salida del hogar ${a.household_code} registrada: cupos liberados.` },
    );
    await load();
  }

  const open = shelters.filter((s) => s.status === "abierto");
  const duplicates = items.filter((a) => a.is_duplicate).length;
  const missingSubsidy = aidType === "subsidio_arriendo" && (!Number(amount) || !months);
  const missingShelter = aidType === "albergue" && !shelterId;

  return (
    <div className="flex flex-col gap-4">
      <Card
        title="Acta de entrega de ayuda humanitaria"
        extra={<span className="text-xs text-tinta-suave">Una entrega por acta</span>}
      >
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              N.º del acta
              <input
                className={input}
                value={act}
                onChange={(e) => setAct(e.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
              />
            </label>
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
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            {(aidType === "mercado" || aidType === "kit") && (
              <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                Cantidad
                <input
                  type="number"
                  min={1}
                  max={100}
                  className={input}
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, Number(e.target.value) || 1))}
                />
              </label>
            )}
            {aidType === "subsidio_arriendo" && (
              <>
                <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                  Valor mensual (pesos)
                  <input
                    type="number"
                    min={0}
                    step={1000}
                    className={input}
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="550000"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-tinta-suave">
                  Meses
                  <input
                    type="number"
                    min={1}
                    max={24}
                    className={input}
                    value={months}
                    onChange={(e) => setMonths(Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
              </>
            )}
            {aidType === "albergue" && (
              <label className="flex flex-col gap-1 text-xs text-tinta-suave sm:col-span-2">
                Albergue de destino (abiertos, con cupos libres)
                <select
                  className={input}
                  value={shelterId}
                  onChange={(e) => setShelterId(e.target.value)}
                >
                  <option value="">Elija…</option>
                  {open.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} · {s.barrio} · {formatInt(s.capacity - s.people)} cupos libres
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Entidad que entrega
              <input
                className={input}
                value={deliveredBy}
                onChange={(e) => setDeliveredBy(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-tinta-suave">
              Fondo
              <input className={input} value={fund} onChange={(e) => setFund(e.target.value)} />
            </label>
            <label className="flex items-center gap-2 self-end pb-2 text-sm">
              <input
                type="checkbox"
                checked={signed}
                onChange={(e) => setSigned(e.target.checked)}
              />
              El jefe de hogar firmó el acta
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
              disabled={
                document.trim().length < 5 ||
                missingSubsidy ||
                missingShelter ||
                (needsJustification && !justification.trim())
              }
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
              <span className="font-medium">{AID_LABEL[a.aid_type]}</span>
              <span className="text-tinta-suave">{detalle(a)}</span>
              {a.is_duplicate && (
                <span
                  className="rounded bg-amber-100 px-1.5 text-xs text-amber-900"
                  title={a.justification ?? ""}
                >
                  Repetida · {a.justification}
                </span>
              )}
              {!a.signed && (
                <span className="rounded bg-senal-fondo px-1.5 text-xs text-senal">
                  Acta sin firma
                </span>
              )}
              <span className="ml-auto flex items-center gap-2 text-xs text-tinta-suave">
                {a.act_number ? `Acta N.º ${a.act_number} · ` : ""}
                {a.delivered_by ? `${a.delivered_by} · ` : ""}
                {formatDateTime(a.at)}
                {a.aid_type === "albergue" && !a.ended_at && (
                  <button
                    type="button"
                    onClick={() => salida(a)}
                    className="rounded border border-linea px-2 py-0.5 text-tinta"
                  >
                    Registrar salida
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
