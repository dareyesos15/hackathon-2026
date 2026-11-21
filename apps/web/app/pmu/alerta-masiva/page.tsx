"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage e id de la alerta en la URL (?id=).
const ReporteAlertaMasiva = dynamic(() => import("./ReporteAlertaMasiva"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando reporte…</p>,
});

export default function AlertaMasivaPage() {
  return <ReporteAlertaMasiva />;
}
