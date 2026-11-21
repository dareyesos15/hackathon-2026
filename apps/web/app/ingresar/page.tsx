"use client";
/** Iniciar sesión: elegir el rol. */
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DEMO_TOKENS, ROLE_LABELS, setSession, type Role } from "@/lib/session";

const DESTINO: Record<Role, { href: string; descripcion: string }> = {
  ciudadano: {
    href: "/reportar/",
    descripcion:
      "Reportar una emergencia, incluso sin señal, y ver el mapa de afectación, las alertas y la predicción de cascada.",
  },
  pmu: {
    href: "/pmu/",
    descripcion:
      "PMU, COE y agencias de respuesta: triaje y verificación, despacho de recursos, alertas oficiales y predicción de cascada.",
  },
  admin: {
    href: "/admin/",
    descripcion: "Simulaciones: reproducir el escenario con datos o empezar sin datos.",
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

export default function Ingresar() {
  const router = useRouter();
  const ahora = useAhora();

  function entrar(role: Role) {
    setSession({ role, token: DEMO_TOKENS[role] });
    router.push(DESTINO[role].href);
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="bg-sangre text-white">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 pt-6 pb-8">
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

      <section className="mx-auto flex w-full max-w-3xl flex-col px-4 py-8">
        <h2 className="mb-3 font-display text-2xl font-semibold">
          Iniciar sesión: ¿cómo vas a entrar?
        </h2>
        <ul className="divide-y divide-linea rounded-md border border-linea bg-white">
          {(Object.keys(DESTINO) as Role[]).map((role) => (
            <li key={role} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <div className="flex-1">
                <h3 className="font-display text-xl font-semibold">{ROLE_LABELS[role]}</h3>
                <p className="text-sm text-tinta-suave">{DESTINO[role].descripcion}</p>
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
      </section>
    </main>
  );
}
