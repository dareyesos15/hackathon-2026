"use client";
/**
 * PWA ciudadana (US4): aviso de privacidad + consentimiento, formulario corto, redacción en el
 * borde, guardado en el teléfono (outbox) y envío automático al volver la señal.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { db, enqueue, flush, newClientUuid, startSync, type OutboxItem } from "@/lib/db";
import { formatTime } from "@/lib/format";
import { CATEGORY_LABEL, type Category } from "@/lib/labels";
import { redact } from "@/lib/redact";
import { DEMO_TOKENS, getSession, setSession } from "@/lib/session";

const CONSENT_KEY = "dacora.consent.v1";
const CATEGORIES: Category[] = [
  "personas_atrapadas",
  "heridos",
  "colapso_estructura",
  "dano_estructural",
  "incendio",
  "fuga_gas",
  "deslizamiento",
  "via_bloqueada",
  "servicios_caidos",
  "necesidad_albergue",
  "necesidad_ayuda",
  "persona_desaparecida",
];

function readConsent(): boolean {
  try {
    return window.localStorage.getItem(CONSENT_KEY) !== null;
  } catch {
    return false;
  }
}

function ensureCitizenSession() {
  const s = getSession();
  if (!s || s.role !== "ciudadano") setSession({ role: "ciudadano", token: DEMO_TOKENS.ciudadano });
}

export default function ReporteCiudadano() {
  const [consent, setConsent] = useState(readConsent);
  const [online, setOnline] = useState(() => navigator.onLine);
  const [barrios, setBarrios] = useState<string[]>([]);
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [category, setCategory] = useState<Category | "">("");
  const [text, setText] = useState("");
  const [barrio, setBarrio] = useState("");
  const [gps, setGps] = useState<{ lat: number; lon: number } | null>(null);
  const [gpsMsg, setGpsMsg] = useState<string | null>(null);
  const [people, setPeople] = useState("");
  const [contact, setContact] = useState("");
  const [photo, setPhoto] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setItems(await db.outbox.orderBy("created_at").reverse().limit(20).toArray());
  }, []);

  useEffect(() => {
    ensureCitizenSession();
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    const stop = startSync(() => void refresh());
    void db.outbox.orderBy("created_at").reverse().limit(20).toArray().then(setItems);
    // Lista de barrios: de la API si hay red; si no, la última copia guardada en el teléfono.
    db.kv.get("barrios").then((cached) => {
      if (Array.isArray(cached?.value)) setBarrios(cached.value as string[]);
    });
    api.GET("/api/v1/geo/barrios").then(({ data }) => {
      const names = (data as { names?: string[] } | undefined)?.names;
      if (names?.length) {
        setBarrios(names);
        void db.kv.put({ key: "barrios", value: names });
      }
    });
    return () => {
      stop();
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, [refresh]);

  const preview = useMemo(() => redact(text), [text]);

  function accept() {
    try {
      window.localStorage.setItem(CONSENT_KEY, new Date().toISOString());
    } catch {
      /* sin almacenamiento: el consentimiento vale para esta sesión */
    }
    setConsent(true);
  }

  function locate() {
    if (!("geolocation" in navigator) || !window.isSecureContext) {
      setGpsMsg("GPS no disponible en esta conexión: elija su barrio.");
      return;
    }
    setGpsMsg("Buscando ubicación…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGps({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setGpsMsg("Ubicación GPS lista.");
      },
      () => setGpsMsg("No se pudo obtener el GPS: elija su barrio."),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!preview.text.trim()) return;
    const peopleN = people === "" ? null : Math.max(0, parseInt(people, 10) || 0);
    await enqueue({
      client_uuid: newClientUuid(),
      channel: "pwa",
      occurred_at: new Date().toISOString(),
      text: preview.text, // ya redactado en el teléfono
      category_hint: category || null,
      location: gps ? { lat: gps.lat, lon: gps.lon, precision: "gps" } : null,
      barrio: gps ? null : barrio || null,
      people_affected: peopleN,
      has_media: photo,
      reporter_contact: contact.trim() || null,
      consent: true,
    });
    setText("");
    setPeople("");
    setPhoto(false);
    setMessage(
      navigator.onLine
        ? "Reporte guardado. Enviando…"
        : "Guardado en su teléfono: se enviará solo cuando haya señal.",
    );
    await refresh();
    if (navigator.onLine) {
      const sent = await flush();
      if (sent) setMessage("Reporte enviado al PMU. Gracias.");
      await refresh();
    }
  }

  if (!consent) {
    return (
      <main className="mx-auto flex max-w-lg flex-col gap-4 px-4 py-8">
        <h1 className="text-2xl font-bold">Reportar una emergencia</h1>
        <section className="rounded-xl bg-white p-4 text-sm">
          <h2 className="font-semibold">Aviso de privacidad (Ley 1581 de 2012)</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-tinta">
            <li>
              Sus reportes se usan solo para atender la emergencia y coordinar la respuesta del
              Puesto de Mando Unificado (PMU).
            </li>
            <li>
              Antes de salir de su teléfono se borran teléfonos, cédulas, correos, placas y nombres
              del texto.
            </li>
            <li>
              Si deja un teléfono de contacto, el sistema guarda solo una huella cifrada para
              reconocer reportes repetidos; nunca el número.
            </li>
            <li>Lo que se publique será agregado por manzana o barrio, nunca individual.</li>
          </ul>
          <p className="mt-2 text-xs text-tinta-suave">
            Prototipo con datos SIMULADOS · Hackathon UNAL Manizales 2026.
          </p>
        </section>
        <button
          type="button"
          onClick={accept}
          className="rounded-lg bg-tinta px-4 py-3 font-medium text-white"
        >
          Acepto y quiero reportar
        </button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-lg flex-col gap-4 px-4 py-6">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="font-display text-2xl font-semibold">Reportar una emergencia</h1>
        <EtiquetaSimulado />
        <span
          className={`ml-auto rounded-sm px-2 py-0.5 text-xs font-bold whitespace-nowrap ${
            online ? "bg-[#e3f1e9] text-verificado" : "bg-[#ffe9b8] text-tinta"
          }`}
        >
          {online ? "Con señal" : "Sin señal"}
        </span>
      </header>

      <form
        onSubmit={submit}
        className="flex flex-col gap-3 rounded-md border border-linea bg-white p-4"
      >
        <label className="text-sm font-medium">
          ¿Qué pasa?
          <select
            className="mt-1 w-full rounded border border-linea bg-white px-2 py-2"
            value={category}
            onChange={(e) => setCategory(e.target.value as Category | "")}
          >
            <option value="">No sé / otra cosa</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c]}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm font-medium">
          Descripción
          <textarea
            required
            rows={3}
            maxLength={1000}
            className="mt-1 w-full rounded border border-linea p-2"
            placeholder="Ej.: se cayó la casa de la calle 30 con carrera 24, hay 2 personas atrapadas"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
        {preview.kinds.length > 0 && (
          <p className="rounded bg-amber-50 p-2 text-xs text-amber-900">
            Por su privacidad se enviará así: “{preview.text}”
          </p>
        )}

        <div className="flex flex-col gap-2 text-sm">
          <span className="font-medium">Ubicación</span>
          <button
            type="button"
            onClick={locate}
            className="rounded border border-linea px-3 py-2 text-left"
          >
            📍 Usar mi ubicación (GPS)
          </button>
          {gpsMsg && <span className="text-xs text-tinta-suave">{gpsMsg}</span>}
          {!gps && (
            <select
              aria-label="Barrio"
              className="rounded border border-linea bg-white px-2 py-2"
              value={barrio}
              onChange={(e) => setBarrio(e.target.value)}
            >
              <option value="">Elegir barrio…</option>
              {barrios.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          )}
        </div>

        <label className="text-sm font-medium">
          Personas afectadas (opcional)
          <input
            type="number"
            min={0}
            inputMode="numeric"
            className="mt-1 w-full rounded border border-linea px-2 py-2"
            value={people}
            onChange={(e) => setPeople(e.target.value)}
          />
        </label>

        <label className="text-sm font-medium">
          Foto (opcional)
          <input
            type="file"
            accept="image/*"
            capture="environment"
            className="mt-1 block w-full text-xs"
            onChange={(e) => setPhoto(Boolean(e.target.files?.length))}
          />
          <span className="text-[11px] font-normal text-tinta-suave">
            En este prototipo la foto se queda en su teléfono; solo se informa que existe.
          </span>
        </label>

        <label className="text-sm font-medium">
          Teléfono de contacto (opcional)
          <input
            type="tel"
            className="mt-1 w-full rounded border border-linea px-2 py-2"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
          />
          <span className="text-[11px] font-normal text-tinta-suave">
            Solo se guarda una huella cifrada para reconocer reportes repetidos.
          </span>
        </label>

        <button
          type="submit"
          className="rounded-lg bg-senal px-4 py-3 hover:bg-sangre-claro font-semibold text-white disabled:opacity-50"
          disabled={!text.trim()}
        >
          Enviar reporte
        </button>
        {message && <p className="text-sm text-tinta">{message}</p>}
      </form>

      <section className="rounded-xl bg-white p-4">
        <h2 className="text-sm font-semibold">Mis reportes en este teléfono</h2>
        <ul className="mt-2 space-y-2 text-xs">
          {items.map((i) => (
            <li key={i.client_uuid} className="flex justify-between gap-2">
              <span className="line-clamp-2 text-tinta">{i.body.text}</span>
              <span
                className={`shrink-0 font-medium ${
                  i.status === "enviado"
                    ? "text-verificado"
                    : i.status === "error"
                      ? "text-senal"
                      : "text-amber-700"
                }`}
              >
                {i.status === "enviado"
                  ? `Enviado ${i.sent_at ? formatTime(i.sent_at) : ""}`
                  : i.status === "error"
                    ? "No aceptado"
                    : "Pendiente de envío"}
              </span>
            </li>
          ))}
          {items.length === 0 && <li className="text-tinta-suave">Aún no ha enviado reportes.</li>}
        </ul>
      </section>
    </main>
  );
}
