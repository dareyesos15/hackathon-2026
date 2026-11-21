"use client";
/** Registra el service worker solo donde el navegador lo permite (https o localhost). */
import { useEffect } from "react";

export function RegistroSW() {
  useEffect(() => {
    if ("serviceWorker" in navigator && window.isSecureContext) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        /* sin service worker la app sigue funcionando con el outbox en IndexedDB */
      });
    }
  }, []);
  return null;
}
