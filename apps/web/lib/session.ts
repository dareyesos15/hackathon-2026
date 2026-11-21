/**
 * Sesión de demo: rol + token fijo (research R9), guardados en sessionStorage del navegador.
 *
 * Tres roles en la interfaz:
 * - `ciudadano`: reporta emergencias (PWA) y ve el inicio público.
 * - `pmu` (Entidades y PMU): PMU, COE y agencias de respuesta en un solo rol. Usa el token `coe`
 *   de la API, que además tiene los permisos del operador y de la agencia; por eso puede
 *   aprobar alertas oficiales (EMRE tarea 5.5) y lo hecho queda en la bitácora como `coe`.
 * - `admin`: lanza simulaciones con datos (escenario) o sin datos (tablero vacío).
 * Sin sesión, la página de inicio consulta como `publico` (solo agregados).
 */

export type Role = "ciudadano" | "pmu" | "admin";

export interface Session {
  role: Role;
  token: string;
}

const KEY = "dacora.session";

/** Tokens de demo (coinciden con .env.example). Solo para el prototipo. */
export const DEMO_TOKENS: Record<Role, string> = {
  ciudadano: "ciudadano-demo",
  pmu: "coe-demo",
  admin: "admin-demo",
};

/** Token del rol `publico` de la API, usado sin sesión (solo datos agregados). */
export const PUBLIC_TOKEN = "publico-demo";

export const ROLE_LABELS: Record<Role, string> = {
  ciudadano: "Ciudadanía",
  pmu: "Entidades y PMU",
  admin: "Administrador",
};

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    const session = raw ? (JSON.parse(raw) as Session) : null;
    // Sesiones de roles que ya no existen (versiones anteriores de la demo) se ignoran.
    return session && session.role in DEMO_TOKENS ? session : null;
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
