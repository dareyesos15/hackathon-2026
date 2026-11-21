/**
 * Cliente REST tipado de la API de Dacora (principio X).
 * Tipos generados desde /openapi.json: `npm run gen:api` (no editar schema.d.ts a mano).
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { PUBLIC_TOKEN, getSession } from "@/lib/session";

/** Mismo origen en producción (Nginx hace proxy de /api/). En `next dev`, apuntar a la API. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/** Sin sesión, la página de inicio consulta como `publico`: solo agregados (k ≥ 5) y KPI. */
const auth: Middleware = {
  onRequest({ request }) {
    const token = getSession()?.token ?? PUBLIC_TOKEN;
    request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: API_BASE });
api.use(auth);

export type { paths, components } from "./schema";
