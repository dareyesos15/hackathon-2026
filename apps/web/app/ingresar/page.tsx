"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { DEMO_TOKENS, ROLE_LABELS, setSession, type Role } from "@/lib/session";

const DESTINO: Record<Role, { href: string; descripcion: string }> = {
  operador_pmu: {
    href: "/pmu/",
    descripcion: "Mapa de daños, matriz de triaje, verificación, despacho y borradores de alerta.",
  },
  coe: {
    href: "/pmu/",
    descripcion: "Tablero del PMU y aprobación de alertas oficiales (solo el COE las emite).",
  },
  agencia: {
    href: "/agencia/",
    descripcion:
      "Despachos asignados a su agencia: llegada, atención finalizada o fuera de servicio.",
  },
  ciudadano: {
    href: "/reportar/",
    descripcion: "Reportar una emergencia, incluso sin señal: se envía al volver la red.",
  },
  publico: {
    href: "/",
    descripcion: "Mapa de afectación por manzana e indicadores agregados con fecha de corte.",
  },
};

export default function Ingresar() {
  const router = useRouter();
  const [tokens, setTokens] = useState<Record<Role, string>>(DEMO_TOKENS);

  function entrar(role: Role) {
    setSession({ role, token: tokens[role] });
    router.push(DESTINO[role].href);
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <Link href="/" className="text-sm text-slate-600 underline">
          ← Volver al mapa y los indicadores
        </Link>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">Dacora · Iniciar sesión</h1>
          <EtiquetaSimulado />
        </div>
        <p className="text-sm text-slate-600">Elija su rol para entrar a su panel.</p>
        <p className="text-slate-600">
          Datos, alerta y coordinación para la respuesta al sismo del 10 de agosto de 2026 en
          Manizales. Prototipo de la Hackathon UNAL Manizales 2026 · Vertical 05.
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(Object.keys(DESTINO) as Role[]).map((role) => (
          <div key={role} className="flex flex-col gap-3 rounded-xl bg-white p-4 shadow-sm">
            <h2 className="font-semibold">{ROLE_LABELS[role]}</h2>
            <p className="flex-1 text-sm text-slate-600">{DESTINO[role].descripcion}</p>
            <label className="text-xs text-slate-500">
              Token de demo
              <input
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs"
                value={tokens[role]}
                onChange={(e) => setTokens({ ...tokens, [role]: e.target.value })}
              />
            </label>
            <button
              type="button"
              onClick={() => entrar(role)}
              className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Entrar
            </button>
          </div>
        ))}
      </section>

      <footer className="text-xs text-slate-500">
        La IA solo sugiere; decide un humano. Ningún dato personal se guarda en claro (Ley 1581 de
        2012). Todos los datos de esta demo son sintéticos.
      </footer>
    </main>
  );
}
