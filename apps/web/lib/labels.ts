/** Textos de interfaz en español de Colombia para valores del contrato (glosario CLAUDE.md §13). */
import type { components } from "@/lib/api/schema";

export type Category = components["schemas"]["Category"];
export type TriageLevel = components["schemas"]["TriageLevel"];
export type TrustLabel = components["schemas"]["TrustLabel"];
export type IncidentStatus = components["schemas"]["IncidentStatus"];
export type Channel = components["schemas"]["Channel"];
export type IncidentSummary = components["schemas"]["IncidentSummary"];
export type IncidentDetail = components["schemas"]["IncidentDetail"];
export type ReportOut = components["schemas"]["ReportOut"];

export const CATEGORY_LABEL: Record<Category, string> = {
  personas_atrapadas: "Personas atrapadas",
  heridos: "Heridos",
  colapso_estructura: "Colapso de estructura",
  dano_estructural: "Daño estructural",
  incendio: "Incendio",
  fuga_gas: "Fuga de gas",
  deslizamiento: "Deslizamiento",
  via_bloqueada: "Vía bloqueada",
  servicios_caidos: "Servicios caídos",
  necesidad_albergue: "Necesidad de albergue",
  necesidad_ayuda: "Necesidad de ayuda",
  persona_desaparecida: "Persona desaparecida",
  sismo_sentido: "Sismo sentido",
  rumor_informacion: "Rumor / información",
  sin_clasificar: "Sin clasificar",
};

export const TRIAGE_LABEL: Record<TriageLevel, string> = {
  critico: "Crítico",
  alto: "Alto",
  medio: "Medio",
  bajo: "Bajo",
};

/** Colores por nivel de triaje (mapa y lista): cuanto más rojo, más urgente. */
export const TRIAGE_COLOR: Record<TriageLevel, string> = {
  critico: "#d21f2b",
  alto: "#ee6a2c",
  medio: "#e8a92a",
  bajo: "#6e7c8c",
};

export const TRIAGE_ORDER: TriageLevel[] = ["critico", "alto", "medio", "bajo"];

export const TRUST_LABEL: Record<TrustLabel, string> = {
  verificado: "Verificado",
  probable: "Probable",
  sin_verificar: "Sin verificar",
  posible_falso: "Posible falso",
};

export const TRUST_STYLE: Record<TrustLabel, string> = {
  verificado: "bg-[#e3f1e9] text-verificado border-[#a9d3bb]",
  probable: "bg-white text-tinta border-linea",
  sin_verificar: "bg-papel text-tinta-suave border-linea border-dashed",
  posible_falso: "bg-tinta text-white border-tinta",
};

export const STATUS_LABEL: Record<IncidentStatus, string> = {
  abierto: "Abierto",
  en_revision: "En revisión",
  verificado: "Verificado",
  descartado: "Descartado",
  atendido: "Atendido",
};

export const CHANNEL_LABEL: Record<Channel, string> = {
  pwa: "App ciudadana",
  sms: "SMS",
  whatsapp: "WhatsApp",
  call_123: "Línea 123",
  entity: "Entidad oficial",
  lora: "Nodo LoRa",
};

export const SIGNAL_LABEL: Record<string, string> = {
  canal: "Confiabilidad del canal",
  fuentes_independientes: "Fuentes independientes",
  consistencia_fisica: "Consistencia física",
  precision_geografica: "Precisión geográfica",
  desinformacion: "Señales de desinformación",
  evidencia: "Evidencia (foto)",
  sensor_campo: "Sensor de campo",
};

// --- Despacho, alertas y cascada (specs/002). Tipos generados desde el OpenAPI. ---

export type EmreFunction = components["schemas"]["EmreFunction"];
export type ResourceType = components["schemas"]["ResourceType"];
export type ResourceStatus = components["schemas"]["ResourceStatus"];
export type DispatchStatus = components["schemas"]["DispatchStatus"];
export type IncidentDispatchStatus = IncidentSummary["dispatch_status"];
export type ResourceOut = components["schemas"]["ResourceOut"];
export type DispatchOut = components["schemas"]["DispatchOut"];
export type DispatchSuggestion = components["schemas"]["DispatchSuggestion"];
export type TrackOut = components["schemas"]["TrackOut"];
export type AgencyOut = components["schemas"]["AgencyOut"];
// Alertas y cascada: espejo del dominio hasta que sus esquemas existan en el contrato.
export type AlertType =
  "evacuacion" | "deslizamiento" | "sismo_replica" | "servicios_publicos" | "informacion_general";
export type AlertStatus = "borrador" | "emitida" | "rechazada" | "anulada";
export type AlertChannel = "tablero" | "mapa_publico" | "sms_cuadrillas";
export type CascadeLevel = "bajo" | "medio" | "alto" | "muy_alto";

export const EMRE_FUNCTION_LABEL: Record<EmreFunction, string> = {
  salvamento_seguridad: "1. Salvamento y seguridad",
  salud_saneamiento: "2. Salud y saneamiento",
  asistencia_social: "3. Asistencia social",
  infraestructura_servicios: "4. Infraestructura, servicios y ambiente",
  manejo_coordinacion: "5. Manejo y coordinación",
  logistica: "6. Logística",
};

export const RESOURCE_TYPE_LABEL: Record<ResourceType, string> = {
  cuadrilla_rescate: "Cuadrilla de rescate",
  maquina_extincion: "Máquina de extinción",
  ambulancia: "Ambulancia",
  patrulla: "Patrulla",
  cuadrilla_tecnica: "Cuadrilla técnica",
  vehiculo_logistico: "Vehículo logístico",
};

export const RESOURCE_STATUS_LABEL: Record<ResourceStatus, string> = {
  disponible: "Disponible",
  en_camino: "En camino",
  en_sitio: "En sitio",
  fuera_de_servicio: "Fuera de servicio",
};

/** Colores de recursos en el mapa. */
export const RESOURCE_STATUS_COLOR: Record<ResourceStatus, string> = {
  disponible: "#16a34a",
  en_camino: "#7c3aed",
  en_sitio: "#0f766e",
  fuera_de_servicio: "#64748b",
};

export const DISPATCH_STATUS_LABEL: Record<DispatchStatus, string> = {
  en_camino: "En camino",
  en_sitio: "En sitio",
  finalizado: "Finalizado",
  cancelado: "Cancelado",
};

export const INCIDENT_DISPATCH_LABEL: Record<IncidentDispatchStatus, string> = {
  sin_despacho: "Sin despacho",
  en_camino: "En camino",
  en_sitio: "En sitio",
  finalizado: "Atención finalizada",
};

export const ALERT_TYPE_LABEL: Record<AlertType, string> = {
  evacuacion: "Evacuación",
  deslizamiento: "Deslizamiento",
  sismo_replica: "Réplica / información sísmica",
  servicios_publicos: "Servicios públicos",
  informacion_general: "Información general",
};

export const ALERT_STATUS_LABEL: Record<AlertStatus, string> = {
  borrador: "Borrador",
  emitida: "Emitida",
  rechazada: "Rechazada",
  anulada: "Anulada",
};

export const ALERT_CHANNEL_LABEL: Record<AlertChannel, string> = {
  tablero: "Tablero del PMU",
  mapa_publico: "Mapa público",
  sms_cuadrillas: "SMS a cuadrillas en campo",
};

export const CASCADE_LEVEL_LABEL: Record<CascadeLevel, string> = {
  bajo: "Bajo",
  medio: "Medio",
  alto: "Alto",
  muy_alto: "Muy alto",
};

export const CASCADE_LEVEL_COLOR: Record<CascadeLevel, string> = {
  bajo: "#bbf7d0",
  medio: "#fde047",
  alto: "#f97316",
  muy_alto: "#7f1d1d",
};

export const CASCADE_LEVEL_ORDER: CascadeLevel[] = ["bajo", "medio", "alto", "muy_alto"];

export const CASCADE_FACTOR_LABEL: Record<string, string> = {
  pendiente: "Pendiente del terreno",
  lluvia: "Lluvia acumulada (3 h)",
  sismo: "Intensidad sísmica",
  reportes_cercanos: "Reportes cercanos",
};

export type AlertOut = components["schemas"]["AlertOut"];
export type AlertEventOut = components["schemas"]["AlertEventOut"];
export type AlertAreaIn = components["schemas"]["AlertAreaIn"];
