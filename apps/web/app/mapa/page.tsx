"use client";

import dynamic from "next/dynamic";

// Solo en el navegador: sesión en sessionStorage y MapLibre.
const MapaPublico = dynamic(() => import("./MapaPublico"), {
  ssr: false,
  loading: () => <p className="p-6 text-sm text-tinta-suave">Cargando mapa…</p>,
});

export default function MapaPage() {
  return <MapaPublico />;
}
