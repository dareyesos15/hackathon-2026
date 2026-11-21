import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { redact } from "@/lib/redact";

interface Case {
  input: string;
  expected: string;
}

const fixture = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "..", "data", "fixtures", "pii_cases.json"), "utf-8"),
) as { cases: Case[] };

describe("redacción en el borde (mismos casos que la API)", () => {
  it.each(fixture.cases)("$input", ({ input, expected }) => {
    expect(redact(input).text).toBe(expected);
  });

  it("es idempotente", () => {
    for (const { input } of fixture.cases) {
      const once = redact(input).text;
      expect(redact(once).text).toBe(once);
    }
  });

  it("reporta los tipos de dato redactados", () => {
    expect(new Set(redact("me llamo Ana, cel 3001234567, correo a@b.co").kinds)).toEqual(
      new Set(["NOMBRE", "TEL", "CORREO"]),
    );
  });
});
