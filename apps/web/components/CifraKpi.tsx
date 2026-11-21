/** KPI del contrato renderizado como `Cifra`, con estado según su meta (principio V). */
import type { Kpi } from "@/lib/useKpi";
import { Cifra, type CifraProps } from "./Cifra";

export function estadoKpi(k: Kpi): CifraProps["estado"] {
  const v = k.value;
  if (v === null || v === undefined) return "neutral";
  switch (k.indicator) {
    case "duplicate_detection_rate":
    case "fake_detection_rate":
      return v > 90 ? "ok" : "alerta";
    case "critical_recall":
      return v >= 98 ? "ok" : "alerta";
    case "critical_auto_discarded":
    case "critical_without_dispatch":
      return v === 0 ? "ok" : "alerta";
    case "p95_processing_ms":
      return v < 1000 ? "ok" : "alerta";
    default:
      return "neutral";
  }
}

export function CifraKpi({ k }: { k: Kpi }) {
  return (
    <Cifra
      etiqueta={k.label}
      valor={k.value ?? null}
      unidad={k.unit}
      fuente={k.source}
      version={k.version}
      corte={k.cutoff_at}
      meta={k.target ?? undefined}
      estado={estadoKpi(k)}
      simulado={k.simulated}
    />
  );
}
