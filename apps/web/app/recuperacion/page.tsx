"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage.
const PanelRecuperacion = dynamic(() => import("./PanelRecuperacion"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Cargando recuperación…</p>,
});

export default function RecuperacionPage() {
  return <PanelRecuperacion />;
}
