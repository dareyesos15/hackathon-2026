/**
 * Cliente REST tipado de la API de Dacora (principio X).
 * Tipos generados desde /openapi.json: `npm run gen:api` (no editar schema.d.ts a mano).
 */
import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { getSession } from "@/lib/session";

/** Mismo origen en producción (Nginx hace proxy de /api/). En `next dev`, apuntar a la API. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

const auth: Middleware = {
  onRequest({ request }) {
    const session = getSession();
    if (session) request.headers.set("Authorization", `Bearer ${session.token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: API_BASE });
api.use(auth);

export type { paths, components } from "./schema";
