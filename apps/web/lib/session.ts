/** Sesión de demo: rol + token fijo (research R9), guardados en sessionStorage del navegador. */

export type Role = "operador_pmu" | "coe" | "agencia" | "ciudadano" | "publico";

export interface Session {
  role: Role;
  token: string;
}

const KEY = "dacora.session";

/** Tokens de demo (coinciden con .env.example). Solo para el prototipo. */
export const DEMO_TOKENS: Record<Role, string> = {
  operador_pmu: "pmu-demo",
  coe: "coe-demo",
  agencia: "agencia-demo",
  ciudadano: "ciudadano-demo",
  publico: "publico-demo",
};

export const ROLE_LABELS: Record<Role, string> = {
  operador_pmu: "Operador del PMU",
  coe: "COE",
  agencia: "Agencia de respuesta",
  ciudadano: "Ciudadanía",
  publico: "Público",
};

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(session: Session): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    /* almacenamiento no disponible: la sesión vive solo en memoria de la página */
  }
}

export function clearSession(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* sin almacenamiento */
  }
}
