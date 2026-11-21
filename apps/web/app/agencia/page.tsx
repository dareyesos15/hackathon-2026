"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage.
const PanelAgencia = dynamic(() => import("./PanelAgencia"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-slate-500">Cargando despachos…</p>,
});

export default function AgenciaPage() {
  return <PanelAgencia />;
}
