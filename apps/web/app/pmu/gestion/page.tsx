"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage y eventos en vivo (SSE).
const GestionIncidentes = dynamic(() => import("./GestionIncidentes"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando gestión de incidentes…</p>,
});

export default function GestionPage() {
  return <GestionIncidentes />;
}
