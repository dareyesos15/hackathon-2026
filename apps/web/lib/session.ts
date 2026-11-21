/**
 * Sesión de demo de entidades y administrador (research R9), guardada en sessionStorage.
 *
 * La ciudadanía NO inicia sesión: ve el tablero público y reporta emergencias como anónima.
 * Entran con usuario y contraseña de prueba (`POST /api/v1/auth/login`):
 * - área `pmu`: PMU y COE (triaje, despacho, alertas, cascada, zonas, KPI y recuperación).
 *   Solo el usuario `coe` aprueba alertas oficiales (EMRE tarea 5.5).
 * - área `agencia`: agencias de respuesta (avisos y despachos de su agencia).
 * - área `admin`: simulaciones de la demo.
 */

export type Area = "pmu" | "agencia" | "admin";

export interface Session {
  role: Area;
  token: string;
  apiRole: string;
  username: string;
  displayName: string;
  organization: string;
  agencyCode: string | null;
}

const KEY = "dacora.session.v2";

export const ROLE_LABELS: Record<Area, string> = {
  pmu: "Entidades y PMU",
  agencia: "Agencia de respuesta",
  admin: "Administrador",
};

/** Página de entrada de cada área. */
export const AREA_HOME: Record<Area, string> = {
  pmu: "/pmu/",
  agencia: "/agencia/",
  admin: "/admin/",
};

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    const session = raw ? (JSON.parse(raw) as Session) : null;
    return session && session.role in AREA_HOME && session.token ? session : null;
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
