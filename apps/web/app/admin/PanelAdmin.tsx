"use client";
/**
 * Panel del administrador de la demo: simulaciones con datos (reproduce el escenario sintético,
 * con lluvia SIMULADA opcional) o sin datos (reinicia y deja el tablero vacío para reportes en
 * vivo). La reproducción corre en el servidor; esta página solo la lanza, la detiene y muestra
 * su avance. Todos los datos son SIMULADOS.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { formatDateTime, formatInt } from "@/lib/format";
import { clearSession, getSession } from "@/lib/session";
import { kpiMap, useKpi } from "@/lib/useKpi";

type Status = components["schemas"]["SimulationStatus"];
type Speed = "normal" | "rapida";

const REFRESH_MS = 2000;

const SPEED_LABEL: Record<Speed, string> = {
  rapida: "Rápida: todo el escenario en ~1 minuto",
  normal: "Normal: 1 hora del evento = 1 minuto (~12 min)",
};

export default function PanelAdmin() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [status, setStatus] = useState<Status | null>(null);
  const [speed, setSpeed] = useState<Speed>("rapida");
  const [rain, setRain] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const allowed = session?.role === "admin";
  const k = kpiMap(useKpi(tick));

  const refresh = useCallback(
    () =>
      api.GET("/api/v1/demo/simulation").then(({ data }) => {
        if (data) setStatus(data);
      }),
    [],
  );

  useEffect(() => {
    if (!allowed) {
      router.replace("/ingresar/");
      return;
    }
    const first = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => {
      void refresh();
      setTick((t) => t + 1);
    }, REFRESH_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [allowed, router, refresh]);

  async function start(mode: "con_datos" | "sin_datos") {
    setBusy(true);
    setError(null);
    const { data, error: err } = await api.POST("/api/v1/demo/simulation", {
      body: { mode, speed, rain },
    });
    setBusy(false);
    if (err) setError((err as { detail?: string }).detail ?? "No se pudo iniciar la simulación");
    else if (data) setStatus(data);
  }

  async function stop() {
    setBusy(true);
    const { data } = await api.POST("/api/v1/demo/simulation/stop");
    setBusy(false);
    if (data) setStatus(data);
  }

  if (!allowed) return null;

  const running = status?.running ?? false;
  const received = k.reports_received;
  const consolidated = k.incidents_consolidated;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-2 text-white">
        <h1 className="font-display text-2xl font-semibold leading-none">Dacora</h1>
        <span className="text-sm text-white/75">Administración de simulaciones</span>
        <EtiquetaSimulado sobreOscuro />
        <nav className="ml-auto flex items-center gap-4 text-sm">
          <Link href="/" className="underline decoration-white/40 underline-offset-4">
            Inicio público
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

      <main className="mx-auto flex w-full max-w-4xl flex-col gap-5 px-4 py-6">
        <section className="grid gap-4 md:grid-cols-2">
          <article className="flex flex-col gap-3 rounded-md border border-linea bg-white p-4">
            <h2 className="font-display text-xl font-semibold">Simulación con datos</h2>
            <p className="text-sm text-tinta-suave">
              Borra los datos actuales y reproduce el escenario sintético: reportes por app, SMS,
              WhatsApp, 123 y entidades, con duplicados y rumores. El mapa, los KPI y la predicción
              de cascada se llenan en vivo.
            </p>
            <fieldset className="flex flex-col gap-1 text-sm">
              <legend className="mb-1 font-medium">Velocidad</legend>
              {(Object.keys(SPEED_LABEL) as Speed[]).map((s) => (
                <label key={s} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="speed"
                    checked={speed === s}
                    onChange={() => setSpeed(s)}
                  />
                  {SPEED_LABEL[s]}
                </label>
              ))}
            </fieldset>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={rain} onChange={(e) => setRain(e.target.checked)} />
              Incluir lluvia SIMULADA (para la predicción de cascada)
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={() => start("con_datos")}
              className="rounded-sm bg-senal px-4 py-2 font-bold text-white hover:bg-sangre-claro disabled:opacity-40"
            >
              {running ? "Reiniciar y reproducir de nuevo" : "Iniciar simulación con datos"}
            </button>
          </article>

          <article className="flex flex-col gap-3 rounded-md border border-linea bg-white p-4">
            <h2 className="font-display text-xl font-semibold">Simulación sin datos</h2>
            <p className="text-sm text-tinta-suave">
              Borra reportes, incidentes, despachos, alertas y lluvia, y devuelve los recursos a su
              base. El tablero queda vacío para una demo en vivo: los reportes entran desde la app
              ciudadana o por SMS. Conserva la geografía y el catálogo de recursos.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() => start("sin_datos")}
              className="mt-auto rounded-sm border border-sangre px-4 py-2 font-bold text-sangre hover:bg-papel disabled:opacity-40"
            >
              Empezar sin datos
            </button>
          </article>
        </section>

        <section className="flex flex-col gap-3 rounded-md border border-linea bg-white p-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-xl font-semibold">Estado</h2>
            <span
              className={`rounded-sm px-2 py-0.5 text-xs font-bold ${
                running ? "bg-senal text-white" : "bg-papel text-tinta"
              }`}
            >
              {running
                ? "Reproduciendo el escenario…"
                : status?.mode
                  ? "Detenida o terminada"
                  : "Sin simulaciones en esta sesión"}
            </span>
            {running && (
              <button
                type="button"
                disabled={busy}
                onClick={stop}
                className="ml-auto rounded-sm border border-linea px-3 py-1 text-sm disabled:opacity-40"
              >
                Detener
              </button>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-tinta-suave">Modo</dt>
              <dd className="font-medium">
                {status?.mode === "con_datos"
                  ? "Con datos"
                  : status?.mode === "sin_datos"
                    ? "Sin datos"
                    : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-tinta-suave">Inicio</dt>
              <dd className="font-medium">
                {status?.started_at ? formatDateTime(status.started_at) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-tinta-suave">Reportes recibidos</dt>
              <dd className="font-display text-2xl font-semibold tabular-nums">
                {received?.value != null ? formatInt(received.value) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-tinta-suave">Incidentes consolidados</dt>
              <dd className="font-display text-2xl font-semibold tabular-nums">
                {consolidated?.value != null ? formatInt(consolidated.value) : "—"}
              </dd>
            </div>
          </dl>
          {status && status.log_tail.length > 0 && (
            <pre className="max-h-48 overflow-y-auto rounded-sm bg-tinta p-3 font-mono text-xs text-white/90">
              {status.log_tail.join("\n")}
            </pre>
          )}
          {status?.exit_code != null && status.exit_code !== 0 && (
            <p className="text-sm text-senal">
              La reproducción terminó con error (código {status.exit_code}). Revise el registro.
            </p>
          )}
          {error && <p className="text-sm text-senal">{error}</p>}
        </section>

        <p className="text-xs text-tinta-suave">
          Para ver la simulación: abra el inicio público o entre como Entidades y PMU en otra
          pestaña. Todos los datos son SIMULADOS (Ley 1581 de 2012: ningún dato personal real).
        </p>
      </main>
    </div>
  );
}
