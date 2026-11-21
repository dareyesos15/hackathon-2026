import { describe, expect, it } from "vitest";
import { formatCop, formatInt, formatNumber, formatPercent, formatTime } from "@/lib/format";

describe("formato es-CO", () => {
  it("usa punto de miles y coma decimal", () => {
    expect(formatInt(1449)).toBe("1.449");
    expect(formatNumber(93.45, 1)).toBe("93,5");
    expect(formatPercent(90)).toMatch(/^90,0\s%$/);
  });
  it("expresa pesos en millones o mil millones", () => {
    expect(formatCop(1_840_000_000_000)).toBe("$ 1.840 mil M");
    expect(formatCop(250_000_000)).toBe("$ 250 M");
    expect(formatCop(90_000)).toBe("$ 90.000");
  });
  it("muestra la hora de Colombia", () => {
    // 12:34 UTC = 7:34 a. m. en Bogotá (UTC−5)
    expect(formatTime("2026-08-10T12:34:00Z")).toMatch(/07:34/);
  });
});
