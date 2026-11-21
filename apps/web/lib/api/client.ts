/**
 * Cliente REST tipado de la API de Dacora (principio X).
 * Tipos generados desde /openapi.json: `npm run gen:api` (no editar schema.d.ts a mano).
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { getSession } from "@/lib/session";

/** Mismo origen en producción (Nginx hace proxy de /api/). En `next dev`, apuntar a la API. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/** Con sesión de entidad, envía su token; sin sesión la solicitud es anónima (rol `publico`). */
const auth: Middleware = {
  onRequest({ request }) {
    const token = getSession()?.token;
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: API_BASE });
api.use(auth);

/**
 * Vista pública y reporte ciudadano: siempre anónimos (sin token), con o sin sesión, para que
 * cualquier visitante vea lo mismo (agregados k ≥ 5, triaje sin datos personales) y para que un
 * reporte ciudadano nunca quede atado a la sesión de una entidad.
 */
export const publicApi = createClient<paths>({ baseUrl: API_BASE });

export type { paths, components } from "./schema";
