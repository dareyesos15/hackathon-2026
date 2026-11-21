"use client";
/**
 * Iniciar sesión de entidades (PMU, COE, agencias) y administrador con usuario y contraseña de
 * prueba. La ciudadanía no inicia sesión: reporta y ve el tablero público sin cuenta.
 */
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { publicApi } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { AREA_HOME, ROLE_LABELS, setSession } from "@/lib/session";

type DemoUsers = components["schemas"]["DemoUserList"];

/** Fecha y hora actuales de Colombia; se calcula en el navegador (la página es estática). */
function useAhora(): Date | null {
  const [ahora, setAhora] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setAhora(new Date());
    tick();
    const timer = setInterval(tick, 30_000);
    return () => clearInterval(timer);
  }, []);
  return ahora;
}

const FECHA = new Intl.DateTimeFormat("es-CO", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "America/Bogota",
});
const HORA = new Intl.DateTimeFormat("es-CO", {
  hour: "numeric",
  minute: "2-digit",
  timeZone: "America/Bogota",
});

export default function Ingresar() {
  const router = useRouter();
  const ahora = useAhora();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoUsers | null>(null);

  useEffect(() => {
    publicApi.GET("/api/v1/auth/demo-users").then(({ data }) => {
      if (data) setDemo(data);
    });
  }, []);

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error: err } = await publicApi.POST("/api/v1/auth/login", {
      body: { username, password },
    });
    setBusy(false);
    if (!data) {
      setError(
        (err as { detail?: string } | undefined)?.detail ??
          "No se pudo iniciar sesión. Intente de nuevo.",
      );
      return;
    }
    setSession({
      role: data.area,
      token: data.token,
      apiRole: data.api_role,
      username: data.username,
      displayName: data.display_name,
      organization: data.organization,
      agencyCode: data.agency_code ?? null,
    });
    router.push(AREA_HOME[data.area]);
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="relative overflow-hidden bg-sangre text-white">
        {/* Grabados decorativos: colibrí (izquierda) y Nevado del Ruiz con cafetal (derecha).
            En pantallas angostas se atenúan para no competir con el texto. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 aspect-[372/287] bg-[url('/img/cabecera-colibri.jpg')] bg-cover bg-left opacity-25 [mask-image:linear-gradient(to_right,black_75%,transparent)] min-[1440px]:opacity-100"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 aspect-[421/287] bg-[url('/img/cabecera-volcan.jpg')] bg-cover bg-right opacity-25 [mask-image:linear-gradient(to_left,black_75%,transparent)] min-[1440px]:opacity-100"
        />
        <div className="relative mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pt-6 pb-8">
          <Link href="/" className="text-sm text-white/80 underline underline-offset-4">
            ← Volver al mapa y los indicadores
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-6xl font-semibold leading-none">Dacora</h1>
            <EtiquetaSimulado sobreOscuro />
          </div>
          <p className="max-w-[60ch] text-lg leading-snug text-white/85">
            Datos, alerta y coordinación para responder a emergencias y recuperarse de crisis en
            Manizales: reportes ciudadanos verificados, agrupados y puestos en el mapa del PMU.
          </p>
          <dl className="grid max-w-lg grid-cols-[auto_auto_1fr] gap-x-8 border-t border-white/25 pt-3 text-sm">
            <div>
              <dt className="text-white/65">Ciudad</dt>
              <dd className="font-display text-2xl font-semibold">Manizales</dd>
            </div>
            <div>
              <dt className="text-white/65">Hoy</dt>
              <dd className="font-display text-2xl font-semibold first-letter:uppercase">
                {ahora ? FECHA.format(ahora) : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-white/65">Hora</dt>
              <dd className="font-display text-2xl font-semibold tabular-nums">
                {ahora ? HORA.format(ahora) : "—"}
              </dd>
            </div>
          </dl>
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
        <div className="rounded-md border border-linea bg-white p-4">
          <h2 className="font-display text-2xl font-semibold">
            ¿Necesita reportar una emergencia?
          </h2>
          <p className="mt-1 text-sm text-tinta-suave">
            No necesita cuenta. Reporte desde el teléfono, incluso sin señal, o llame al 123.
          </p>
          <Link
            href="/reportar/"
            className="mt-3 inline-block rounded-sm bg-senal px-5 py-2.5 font-bold text-white hover:bg-sangre-claro"
          >
            Reportar una emergencia
          </Link>
        </div>

        <form
          onSubmit={entrar}
          className="flex flex-col gap-3 rounded-md border border-linea bg-white p-4"
        >
          <h2 className="font-display text-2xl font-semibold">Iniciar sesión de entidades</h2>
          <p className="text-sm text-tinta-suave">
            PMU, COE, agencias de respuesta y administración de la demo.
          </p>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Usuario
            <input
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="rounded-sm border border-linea px-3 py-2 font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-sm border border-linea px-3 py-2 font-normal"
            />
          </label>
          {error && <p className="text-sm text-senal">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="self-start rounded-sm bg-senal px-6 py-2.5 font-bold text-white hover:bg-sangre-claro disabled:opacity-40"
          >
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>

        {demo && demo.items.length > 0 && (
          <div className="rounded-md border border-dashed border-linea bg-papel p-4 text-sm">
            <h2 className="font-semibold">Usuarios de prueba (demo)</h2>
            {demo.password_hint && (
              <p className="mt-1 text-tinta-suave">
                Contraseña para todos: <code className="font-mono">{demo.password_hint}</code>
              </p>
            )}
            <ul className="mt-2 divide-y divide-linea">
              {demo.items.map((u) => (
                <li key={u.username} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                  <button
                    type="button"
                    onClick={() => {
                      setUsername(u.username);
                      if (demo.password_hint) setPassword(demo.password_hint);
                    }}
                    className="font-mono font-bold text-sangre underline underline-offset-4"
                    aria-label={`Usar el usuario de prueba ${u.username}`}
                  >
                    {u.username}
                  </button>
                  <span>{u.organization}</span>
                  <span className="text-xs text-tinta-suave">
                    {ROLE_LABELS[u.area]}
                    {u.api_role === "coe" ? " · aprueba alertas oficiales" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}
