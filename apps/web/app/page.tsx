"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { DEMO_TOKENS, ROLE_LABELS, setSession, type Role } from "@/lib/session";

const DESTINO: Record<Role, { href: string; descripcion: string }> = {
  operador_pmu: {
    href: "/pmu/",
    descripcion: "Mapa de daños, matriz de triaje, verificación y decisión humana.",
  },
  ciudadano: {
    href: "/reportar/",
    descripcion: "Reportar una emergencia, incluso sin señal: se envía al volver la red.",
  },
  publico: {
    href: "/mapa/",
    descripcion: "Mapa de afectación por manzana e indicadores agregados con fecha de corte.",
  },
};

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

export default function Inicio() {
  const router = useRouter();
  const ahora = useAhora();
  const [tokens, setTokens] = useState<Record<Role, string>>(DEMO_TOKENS);

  function entrar(role: Role) {
    setSession({ role, token: tokens[role] });
    router.push(DESTINO[role].href);
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="bg-sangre text-white">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pt-10 pb-8">
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

      <section className="mx-auto flex w-full max-w-3xl flex-col px-4 py-8">
        <h2 className="mb-3 font-display text-2xl font-semibold">¿Cómo vas a entrar?</h2>
        <ul className="divide-y divide-linea rounded-md border border-linea bg-white">
          {(Object.keys(DESTINO) as Role[]).map((role) => (
            <li key={role} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <div className="flex-1">
                <h3 className="font-display text-xl font-semibold">{ROLE_LABELS[role]}</h3>
                <p className="text-sm text-tinta-suave">{DESTINO[role].descripcion}</p>
                <details className="mt-1 text-xs text-tinta-suave">
                  <summary className="cursor-pointer">Token de demo</summary>
                  <input
                    aria-label={`Token de demo para ${ROLE_LABELS[role]}`}
                    className="mt-1 w-full max-w-xs rounded-sm border border-linea px-2 py-1 font-mono text-xs"
                    value={tokens[role]}
                    onChange={(e) => setTokens({ ...tokens, [role]: e.target.value })}
                  />
                </details>
              </div>
              <button
                type="button"
                onClick={() => entrar(role)}
                aria-label={`Entrar: ${ROLE_LABELS[role]}`}
                className="rounded-sm bg-senal px-6 py-2.5 font-bold text-white hover:bg-sangre-claro"
              >
                Entrar
              </button>
            </li>
          ))}
        </ul>

        <p className="mt-6 max-w-[65ch] text-sm text-tinta-suave">
          La IA solo sugiere; decide un humano. Ningún dato personal se guarda en claro (Ley 1581 de
          2012). Todos los datos de esta demo son sintéticos.
        </p>
      </section>
    </main>
  );
}
