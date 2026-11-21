"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

// El mapa público ahora es la página de inicio (`/`).
export default function MapaPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/");
  }, [router]);
  return null;
}
