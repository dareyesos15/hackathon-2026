import type { Metadata, Viewport } from "next";
import { RegistroSW } from "@/components/RegistroSW";
// Fuentes empaquetadas en el build (sin Google Fonts en tiempo de ejecución: offline-first).
import "@fontsource/atkinson-hyperlegible/latin-400.css";
import "@fontsource/atkinson-hyperlegible/latin-700.css";
import "@fontsource/barlow-semi-condensed/latin-500.css";
import "@fontsource/barlow-semi-condensed/latin-600.css";
import "@fontsource/barlow-semi-condensed/latin-700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dacora · Datos, alerta y coordinación",
  description:
    "Tablero situacional y reporte ciudadano para responder a emergencias y recuperarse de crisis en Manizales. Prototipo con datos SIMULADOS.",
  manifest: "/manifest.json",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#5c0f1b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-CO" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-papel text-tinta">
        <RegistroSW />
        {children}
      </body>
    </html>
  );
}
