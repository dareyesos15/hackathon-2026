/** Textos y tipos del módulo de recuperación (specs/003). */
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type InspectionColor = S["InspectionColor"];
export type DamageLevel = S["DamageLevel"];
export type AidType = S["AidType"];
export type RudStatus = S["RudStatus"];
export type PropertyOut = S["PropertyOut"];
export type InspectionOut = S["InspectionOut"];
export type HouseholdOut = S["HouseholdOut"];
export type AidOut = S["AidOut"];
export type ShelterOut = S["ShelterOut"];
export type ManzanaRef = S["ManzanaRef"];
export type RecoverySummary = S["RecoverySummary"];

export const COLOR_LABEL: Record<InspectionColor, string> = {
  verde: "Verde · habitable",
  amarillo: "Amarillo · uso restringido",
  rojo: "Rojo · no habitable",
};

export const COLOR_HEX: Record<InspectionColor, string> = {
  verde: "#2f7d55",
  amarillo: "#e8a92a",
  rojo: "#d21f2b",
};

export const DAMAGE_LABEL: Record<DamageLevel, string> = {
  menor: "Menor",
  mediano_uso_restringido: "Mediano (uso restringido)",
  mayor: "Mayor",
  colapso: "Colapso",
};

/** Daños compatibles con cada color (espejo de app/core/recovery.py). */
export const COLOR_DAMAGE: Record<InspectionColor, DamageLevel[]> = {
  verde: ["menor"],
  amarillo: ["menor", "mediano_uso_restringido"],
  rojo: ["mediano_uso_restringido", "mayor", "colapso"],
};

export const AID_LABEL: Record<AidType, string> = {
  subsidio_arriendo: "Subsidio de arriendo",
  kit: "Kit de aseo / cocina",
  mercado: "Mercado",
  albergue: "Cupo en albergue",
};

export const RUD_LABEL: Record<RudStatus, string> = {
  pendiente: "RUD pendiente",
  inscrito: "Inscrito en RUD",
};

export const VULN_LABEL = {
  children: "Niñez",
  elderly: "Adulto mayor",
  disability: "Discapacidad",
  pregnancy: "Gestante",
} as const;

export function errorText(err: unknown, fallback: string): string {
  return (err as { detail?: string } | undefined)?.detail ?? fallback;
}

// ------------------------------------------------------------- tablero unificado

export type RecoveryDashboard = S["RecoveryDashboard"];
export type DashFigure = S["DashFigure"];
export type DashIndicator = S["Indicator"];
export type Need = S["Need"];
export type BarrioRecovery = S["BarrioRecovery"];
export type CurvePoint = S["CurvePoint"];
export type Stage = S["Stage"];
export type StageStatus = Stage["status"];

export const SERVICE_LABEL = {
  agua: "Agua",
  energia: "Energía",
  gas: "Gas",
  telecom: "Telecom.",
  vias: "Vías",
} as const;

export type ServiceKey = keyof typeof SERVICE_LABEL;

/** Semáforo de etapas: siempre con texto, el color no va solo. */
export const STAGE_STATUS: Record<StageStatus, { label: string; hex: string }> = {
  verde: { label: "A tiempo", hex: "#2f7d55" },
  amarillo: { label: "Con retraso", hex: "#e8a92a" },
  rojo: { label: "Estancada", hex: "#d21f2b" },
  pendiente: { label: "Aún no empieza", hex: "#b9adab" },
};

export const NEED_SEVERITY: Record<Need["severity"], { label: string; cls: string }> = {
  critica: { label: "Crítica", cls: "border-senal bg-senal-fondo text-senal" },
  alta: { label: "Alta", cls: "border-amber-300 bg-amber-50 text-amber-900" },
  media: { label: "Media", cls: "border-linea bg-white text-tinta" },
};

export const CHANNEL_LABEL: Record<string, string> = {
  pwa: "App ciudadana",
  sms: "SMS",
  whatsapp: "WhatsApp",
  call_123: "Línea 123",
  entity: "Entidades",
  lora: "LoRa",
};
