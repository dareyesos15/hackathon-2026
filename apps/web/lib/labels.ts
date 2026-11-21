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
  scraping: "Redes/medios",
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
