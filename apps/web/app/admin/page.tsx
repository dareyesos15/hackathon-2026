"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage.
const PanelAdmin = dynamic(() => import("./PanelAdmin"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando…</p>,
});

export default function AdminPage() {
  return <PanelAdmin />;
}
