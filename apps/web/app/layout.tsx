import type { Metadata, Viewport } from "next";
import { RegistroSW } from "@/components/RegistroSW";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dacora · Datos, alerta y coordinación",
  description:
    "Tablero situacional y reporte ciudadano para la recuperación post-sismo de Manizales. Prototipo con datos SIMULADOS.",
  manifest: "/manifest.json",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-CO" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-slate-50 text-slate-900">
        <RegistroSW />
        {children}
      </body>
    </html>
  );
}
