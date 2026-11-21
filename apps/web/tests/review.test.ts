import { describe, expect, it } from "vitest";
import { reviewInconsistency, suggestSemaphore } from "@/lib/recovery";

describe("revisión a predio (formato GUE-RPD-FR-02)", () => {
  it("sugiere el semáforo con la afectación y la evacuación", () => {
    expect(suggestSemaphore("ninguna", false)).toEqual(["verde", "menor"]);
    expect(suggestSemaphore("parcial", false)[0]).toBe("amarillo");
    expect(suggestSemaphore("parcial", true)[0]).toBe("rojo");
    expect(suggestSemaphore("total", false)[0]).toBe("rojo");
  });
  it("rechaza las mismas combinaciones incoherentes que la API", () => {
    expect(reviewInconsistency("amarillo", "parcial", true)).not.toBeNull();
    expect(reviewInconsistency("verde", "ninguna", true)).not.toBeNull();
    expect(reviewInconsistency("amarillo", "total", false)).not.toBeNull();
    expect(reviewInconsistency("rojo", "parcial", true)).toBeNull();
  });
});
