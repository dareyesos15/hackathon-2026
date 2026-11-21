"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage, eventos en vivo (SSE) y MapLibre.
const TableroPmu = dynamic(() => import("./TableroPmu"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Cargando tablero…</p>,
});

export default function PmuPage() {
  return <TableroPmu />;
}
