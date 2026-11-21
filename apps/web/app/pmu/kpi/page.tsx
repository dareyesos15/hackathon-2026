"use client";

import dynamic from "next/dynamic";

const PanelKpi = dynamic(() => import("./PanelKpi"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando indicadores…</p>,
});

export default function KpiPage() {
  return <PanelKpi />;
}
