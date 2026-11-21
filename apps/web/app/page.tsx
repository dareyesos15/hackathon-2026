"use client";

import dynamic from "next/dynamic";

// Página de inicio pública: mapa e indicadores para todos, sin iniciar sesión.
// Solo en el navegador (MapLibre y sessionStorage).
const InicioPublico = dynamic(() => import("./InicioPublico"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Cargando Dacora…</p>,
});

export default function Inicio() {
  return <InicioPublico />;
}
