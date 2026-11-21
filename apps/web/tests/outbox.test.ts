import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import { DacoraDB, enqueue, flush, type ReportIn, type Sender } from "@/lib/db";

function report(text: string): ReportIn {
  return {
    client_uuid: crypto.randomUUID(),
    channel: "pwa",
    text,
    consent: true,
    has_media: false,
  };
}

let database: DacoraDB;

beforeEach(async () => {
  database = new DacoraDB(`prueba-${crypto.randomUUID()}`);
  await database.open();
});

describe("outbox offline", () => {
  it("guarda sin red y queda pendiente", async () => {
    await enqueue(report("hay heridos en Chipre"), database);
    const offline: Sender = async () => {
      throw new Error("sin red");
    };
    expect(await flush(offline, database)).toBe(0);
    const [item] = await database.outbox.toArray();
    expect(item.status).toBe("pendiente");
    expect(item.attempts).toBe(1);
  });

  it("al volver la red envía una sola vez por client_uuid", async () => {
    const a = await enqueue(report("huele a gas"), database);
    const received: string[] = [];
    const online: Sender = async (items) => {
      received.push(...items.map((i) => i.client_uuid));
      return items.map((i) => ({ client_uuid: i.client_uuid, status: "created" as const }));
    };
    expect(await flush(online, database)).toBe(1);
    expect(await flush(online, database)).toBe(0);
    expect(received).toEqual([a.client_uuid]);
    expect((await database.outbox.get(a.client_uuid))?.status).toBe("enviado");
  });

  it("borra el teléfono de contacto del dispositivo al enviar", async () => {
    const a = await enqueue({ ...report("hay heridos"), reporter_contact: "3001234567" }, database);
    await flush(
      async (items) =>
        items.map((i) => ({ client_uuid: i.client_uuid, status: "created" as const })),
      database,
    );
    expect((await database.outbox.get(a.client_uuid))?.body.reporter_contact).toBeNull();
  });

  it("un duplicado del servidor cuenta como enviado; un rechazo queda en error", async () => {
    const a = await enqueue(report("uno"), database);
    const b = await enqueue(report("dos"), database);
    const send: Sender = async () => [
      { client_uuid: a.client_uuid, status: "duplicate" },
      { client_uuid: b.client_uuid, status: "error", error: "consent_required" },
    ];
    await flush(send, database);
    expect((await database.outbox.get(a.client_uuid))?.status).toBe("enviado");
    const failed = await database.outbox.get(b.client_uuid);
    expect(failed?.status).toBe("error");
    expect(failed?.error).toBe("consent_required");
  });
});
