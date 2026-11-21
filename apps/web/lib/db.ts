/**
 * Almacenamiento en el dispositivo (offline-first, principio II): outbox de reportes en IndexedDB.
 * Cada reporte lleva un `client_uuid` generado aquí; la API es idempotente por ese valor, así
 * que reenviar nunca duplica (data-model.md Report.client_uuid). El texto llega ya redactado.
 */
import Dexie, { type Table } from "dexie";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type ReportIn = components["schemas"]["ReportIn"];
export type OutboxStatus = "pendiente" | "enviado" | "error";

export interface OutboxItem {
  client_uuid: string;
  body: ReportIn;
  status: OutboxStatus;
  created_at: string;
  sent_at?: string;
  attempts: number;
  error?: string;
}

export interface KvItem {
  key: string;
  value: unknown;
}

class DacoraDB extends Dexie {
  outbox!: Table<OutboxItem, string>;
  kv!: Table<KvItem, string>;

  constructor(name = "dacora") {
    super(name);
    this.version(1).stores({
      outbox: "client_uuid, status, created_at",
      kv: "key",
    });
  }
}

export const db = new DacoraDB();

export function newClientUuid(): string {
  return crypto.randomUUID();
}

/** Guarda un reporte en la cola local. Funciona sin red. */
export async function enqueue(body: ReportIn, database: DacoraDB = db): Promise<OutboxItem> {
  const item: OutboxItem = {
    client_uuid: body.client_uuid,
    body,
    status: "pendiente",
    created_at: new Date().toISOString(),
    attempts: 0,
  };
  await database.outbox.put(item);
  return item;
}

export type BatchResult = components["schemas"]["BatchItemResult"];
export type Sender = (items: ReportIn[]) => Promise<BatchResult[]>;

/** Envío real: POST /api/v1/ingest/batch (lanza si no hay red o el servidor falla). */
export const sendBatch: Sender = async (items) => {
  const { data, error } = await api.POST("/api/v1/ingest/batch", { body: { items } });
  if (error || !data) throw new Error("No se pudo sincronizar");
  return data.results;
};

let flushing = false;

/**
 * Envía los pendientes (máx. 50 por lote). Si no hay red, quedan pendientes para el
 * siguiente intento; los rechazos de validación quedan como error (no se reintentan).
 */
export async function flush(send: Sender = sendBatch, database: DacoraDB = db): Promise<number> {
  if (flushing) return 0;
  flushing = true;
  try {
    const pending = await database.outbox.where("status").equals("pendiente").limit(50).toArray();
    if (!pending.length) return 0;
    let results: BatchResult[];
    try {
      results = await send(pending.map((p) => p.body));
    } catch {
      await database.outbox.bulkPut(pending.map((p) => ({ ...p, attempts: p.attempts + 1 })));
      return 0;
    }
    const byId = new Map(results.map((r) => [r.client_uuid, r]));
    const now = new Date().toISOString();
    let sent = 0;
    await database.outbox.bulkPut(
      pending.map((p) => {
        const r = byId.get(p.client_uuid);
        if (!r) return { ...p, attempts: p.attempts + 1 };
        if (r.status === "error") {
          return { ...p, status: "error", error: r.error ?? "rechazado", attempts: p.attempts + 1 };
        }
        sent += 1;
        // Ya enviado: el teléfono de contacto no se conserva en el dispositivo.
        return {
          ...p,
          body: { ...p.body, reporter_contact: null },
          status: "enviado",
          sent_at: now,
          attempts: p.attempts + 1,
        };
      }),
    );
    return sent;
  } finally {
    flushing = false;
  }
}

/** Sincroniza al cargar, al volver la red (`online`) y cada 15 s. Devuelve cómo detenerlo. */
export function startSync(onChange?: () => void, intervalMs = 15000): () => void {
  const run = () =>
    void flush().then((n) => {
      if (n > 0) onChange?.();
    });
  run();
  window.addEventListener("online", run);
  const timer = setInterval(run, intervalMs);
  return () => {
    window.removeEventListener("online", run);
    clearInterval(timer);
  };
}

export { DacoraDB };
