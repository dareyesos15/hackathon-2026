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
  kit: "Kit de aseo y cocina",
  mercado: "Kit alimentario (mercado)",
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
export type ContractRow = S["ContractRow"];
export type SourceInfo = S["SourceInfo"];
export type ScenarioComparison = S["ScenarioComparison"];
export type ScenarioSummary = S["ScenarioSummary"];
export type ConfidenceStat = S["ConfidenceStat"];
export type ScenarioKey = "real" | "mejor" | "peor";

export const SCENARIO_LABEL: Record<ScenarioKey, string> = {
  real: "Datos reales",
  mejor: "Mejor caso",
  peor: "Peor caso",
};

/** Semáforo de etapas: siempre con texto, el color no va solo. */
export const STAGE_STATUS: Record<StageStatus, { label: string; hex: string }> = {
  verde: { label: "A tiempo", hex: "#2f7d55" },
  amarillo: { label: "Con retraso", hex: "#e8a92a" },
  rojo: { label: "Estancada", hex: "#d21f2b" },
  pendiente: { label: "Aún no empieza", hex: "#b9adab" },
  sin_fuente: { label: "Sin fuente para medir", hex: "#ffffff" },
};

export const SOURCE_STATUS: Record<SourceInfo["status"], string> = {
  conectada: "Conectada",
  sin_copia: "Sin copia descargada",
  sin_convenio: "Requiere convenio",
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

// ------------------------------------------------- revisión a predio (formato GUE-RPD-FR-02 v4)

export type PropertyReviewIn = S["PropertyReviewIn"];
export type PropertyReviewOut = S["PropertyReviewOut"];
export type ReferralList = S["ReferralList"];
export type ReferralRow = S["ReferralRow"];
export type Affectation = S["Affectation"];
export type EventType = S["EventType"];
export type EventStatus = S["EventStatus"];
export type StructuralCause = S["StructuralCause"];
export type ReferralEntity = S["ReferralEntity"];
export type RespondentRelation = S["RespondentRelation"];
export type AffectedInfrastructure = S["AffectedInfrastructure"];

export const RELATION_LABEL: Record<RespondentRelation, string> = {
  propietario: "Propietario",
  arrendatario: "Arrendatario",
  sucesion: "Sucesión",
  otro: "Otro",
};

export const EVENT_STATUS_LABEL: Record<EventStatus, string> = {
  inminente: "Inminente",
  sucedido: "Sucedido",
};

export const EVENT_TYPE_LABEL: Record<EventType, string> = {
  sismo: "Sismo",
  deslizamiento: "Deslizamiento",
  incendio: "Incendio",
  vendaval: "Vendaval",
  avalancha: "Avalancha",
  inundacion: "Inundación",
  otro: "Otro",
};

export const CAUSE_LABEL: Record<StructuralCause, string> = {
  falta_mantenimiento: "Falta de mantenimiento",
  intervencion_antropica: "Intervención antrópica",
  evento_natural: "Evento natural",
};

export const AFFECTATION_LABEL: Record<Affectation, string> = {
  total: "Total",
  parcial: "Parcial",
  ninguna: "Ninguna",
};

export const INFRA_LABEL: Record<AffectedInfrastructure, string> = {
  vivienda: "Infraestructura de vivienda",
  vial: "Infraestructura vial",
  educativa: "Infraestructura educativa",
  comunitaria: "Infraestructura comunitaria",
};

export const ENTITY_LABEL: Record<ReferralEntity, string> = {
  ugr: "UGR",
  corpocaldas: "Corpocaldas",
  aguas_de_manizales: "Aguas de Manizales",
  obras_publicas: "Obras Públicas Municipales",
  invias: "Invías",
  chec: "CHEC",
  invama: "Invama",
  planeacion: "Planeación",
  infraestructura_depto: "Sec. Infraestructura Depto.",
  inspeccion_policia: "Inspección de Policía",
  otro: "Otra entidad",
};

/** Semáforo sugerido por la afectación y la evacuación (espejo de app/core/recovery.py). */
export function suggestSemaphore(
  affectation: Affectation,
  evacuation: boolean,
): [InspectionColor, DamageLevel] {
  if (affectation === "ninguna" && !evacuation) return ["verde", "menor"];
  if (affectation === "parcial" && !evacuation) return ["amarillo", "mediano_uso_restringido"];
  return ["rojo", "mayor"];
}

/** Combinaciones que el formato no admite (espejo de la API). `null` si es coherente. */
export function reviewInconsistency(
  color: InspectionColor,
  affectation: Affectation,
  evacuation: boolean,
): string | null {
  if (evacuation && color !== "rojo")
    return "Si se recomienda evacuar, el predio no es habitable: el semáforo debe ser rojo.";
  if (affectation === "ninguna" && evacuation) return "Sin afectación no se recomienda evacuación.";
  if (affectation === "ninguna" && color !== "verde")
    return "Sin afectación el semáforo debe ser verde.";
  if (affectation === "total" && color !== "rojo")
    return "Con afectación total el semáforo debe ser rojo.";
  return null;
}

// ---------------------------------------- censo (RUD), actas de entrega y albergues (EMRE 3.1–3.3)

export type Tenure = S["Tenure"];
export type HousingStatus = S["HousingStatus"];
export type HouseholdLoss = S["HouseholdLoss"];
export type ShelterService = S["ShelterService"];
export type ShelterStatus = S["ShelterStatus"];

export const TENURE_LABEL: Record<Tenure, string> = {
  propietario: "Propietario",
  arrendatario: "Arrendatario",
  poseedor: "Poseedor",
  ocupante: "Ocupante",
  otro: "Otro",
};

export const HOUSING_STATUS_LABEL: Record<HousingStatus, string> = {
  habitable: "Habitable",
  no_habitable: "No habitable",
  destruida: "Destruida",
};

export const LOSS_LABEL: Record<HouseholdLoss, string> = {
  enseres: "Enseres",
  herramientas_trabajo: "Herramientas de trabajo",
  animales: "Animales",
  cultivos: "Cultivos",
  vehiculo: "Vehículo",
};

export const SERVICE_LABEL: Record<ShelterService, string> = {
  agua: "Agua",
  energia: "Energía",
  banos: "Baños",
  cocina: "Cocina",
  atencion_salud: "Atención en salud",
  zona_mascotas: "Zona de mascotas",
  zona_infantil: "Zona infantil",
};

export const SITUATION_LABEL: Record<string, { label: string; cls: string }> = {
  albergue: { label: "En albergue", cls: "bg-sky-100 text-sky-900" },
  arriendo: { label: "En arriendo temporal", cls: "bg-indigo-100 text-indigo-900" },
  casa: { label: "En su vivienda", cls: "bg-emerald-100 text-emerald-900" },
  sin_solucion: { label: "Sin solución de vivienda", cls: "bg-senal-fondo text-senal" },
};
