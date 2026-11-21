"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: IndexedDB, geolocalización y estado de conexión.
const ReporteCiudadano = dynamic(() => import("./ReporteCiudadano"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando…</p>,
});

export default function ReportarPage() {
  return <ReporteCiudadano />;
}
