"use client";
/**
 * Alerta masiva de toda la ciudad: sesión de operación propia del PMU (triaje, cascada y zonas
 * solo de esa alerta) y reporte final de problemas, trazabilidad y tiempos de solución.
 */
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import type { IncidentSummary } from "@/lib/labels";

export type MassAlertOut = components["schemas"]["MassAlertOut"];
export type MassAlertEvent = components["schemas"]["MassAlertEvent"];
export type MassAlertIn = components["schemas"]["MassAlertIn"];

/** Sesión del tablero: la operación ordinaria o el id de una alerta masiva. */
export type SessionId = "ordinaria" | string;
export const ORDINARY: SessionId = "ordinaria";

export const MASS_EVENT_LABEL: Record<MassAlertEvent, string> = {
  sismo: "Sismo",
  deslizamientos: "Deslizamientos",
  inundacion: "Inundación",
  ceniza_volcanica: "Ceniza volcánica",
  incendio_estructural: "Incendios estructurales",
  otro: "Otro evento",
};

export function inSession(incident: IncidentSummary, session: SessionId): boolean {
  return session === ORDINARY ? !incident.mass_alert_id : incident.mass_alert_id === session;
}

/** Alertas masivas (activa y anteriores); se recarga con cada evento `mass_alert.changed`. */
export function useMassAlerts(enabled: boolean, revision: number) {
  const [items, setItems] = useState<MassAlertOut[]>([]);
  const [active, setActive] = useState<MassAlertOut | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    api.GET("/api/v1/mass-alerts").then(({ data }) => {
      if (!alive || !data) return;
      setItems(data.items);
      setActive(data.active ?? null);
      setLoaded(true);
    });
    return () => {
      alive = false;
    };
  }, [enabled, revision]);
  return { items, active, loaded };
}

// ------------------------------------------------------------------ reporte (JSON del backend)

export interface TimeStats {
  n: number;
  promedio: number | null;
  mediana: number | null;
  maximo: number | null;
}

export interface TraceEntry {
  at: string;
  accion: string;
  rol: string;
  reportes: number;
  nota: string | null;
}

export interface ProblemDispatch {
  agencia: string;
  agencia_nombre: string;
  recurso: string;
  estado: string;
  refuerzo: boolean;
  creado_at: string;
  llegada_at: string | null;
  cierre_at: string | null;
  distancia_m: number;
}

export interface Problem {
  incident_id: string;
  categoria: string;
  triaje: string;
  riesgo_vital: boolean;
  barrio: string | null;
  manzana_id: string | null;
  estado_final: string;
  reportes: number;
  fuentes_independientes: number;
  personas_afectadas: number | null;
  trust_score: number;
  registrado_at: string;
  verificado_at: string | null;
  primer_despacho_at: string | null;
  primera_llegada_at: string | null;
  cerrado_at: string | null;
  min_a_verificacion: number | null;
  min_a_despacho: number | null;
  min_a_llegada: number | null;
  min_a_solucion: number | null;
  despachos: ProblemDispatch[];
  bitacora: TraceEntry[];
}

export interface MassAlertReportBody {
  version: number;
  preliminar: boolean;
  generado_at: string;
  corte_at: string;
  fuente: string;
  alerta: {
    id: string;
    titulo: string;
    evento: MassAlertEvent;
    descripcion: string | null;
    inicio_at: string;
    fin_at: string | null;
    duracion_min: number | null;
    creada_por: string;
  };
  resumen: {
    incidentes: number;
    reportes: number;
    atendidos: number;
    descartados: number;
    abiertos: number;
    riesgo_vital: number;
    despachos: number;
    por_triaje: Record<string, number>;
    por_categoria: Record<string, number>;
    por_barrio: Record<string, number>;
    por_canal: Record<string, number>;
    por_agencia: Record<string, number>;
  };
  tiempos: {
    solucion: TimeStats;
    verificacion: TimeStats;
    despacho: TimeStats;
    llegada: TimeStats;
    solucion_por_triaje: Record<string, TimeStats>;
  };
  problemas: Problem[];
}

export const TRACE_ACTION_LABEL: Record<string, string> = {
  ingerido: "Reporte recibido",
  agrupado: "Reporte agrupado (duplicado)",
  confirmar: "Confirmado",
  descartar: "Descartado",
  marcar_duplicado: "Marcado como duplicado",
  reabrir: "Reabierto",
  despachar: "Despacho",
  reforzar: "Refuerzo",
  despacho_estado: "Cambio de estado del despacho",
  cancelar_despacho: "Despacho cancelado",
  despacho_doble_bloqueado: "Despacho doble bloqueado",
  cerrar_atendido: "Cerrado como atendido",
};

export const ROLE_LABEL: Record<string, string> = {
  sistema: "Sistema",
  operador_pmu: "PMU",
  coe: "COE",
  agencia: "Agencia",
  inspector: "Inspector",
  publico: "Ciudadanía",
  ciudadano: "Ciudadanía",
};

/** "45 min", "2 h 05 min" o "—". */
export function formatMinutes(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 60) return `${value.toLocaleString("es-CO", { maximumFractionDigits: 1 })} min`;
  const h = Math.floor(value / 60);
  const m = Math.round(value % 60);
  return `${h} h ${String(m).padStart(2, "0")} min`;
}
