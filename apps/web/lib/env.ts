/**
 * Configuración de compilación del frontend (exportación estática: se fija al construir).
 *
 * `NEXT_PUBLIC_DEMO_MODE`: con `true` (por defecto) se marca como "SIMULADO" todo dato, capa o
 * canal sintético (principio IV de la constitución); con `false`, para un despliegue con datos
 * reales, esas marcas no se muestran.
 */
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";

/** Devuelve `text` solo en modo demo (p. ej. sufijos " (SIMULADA)"). */
export function simulado(text: string): string {
  return DEMO_MODE ? text : "";
}
