/** Formato es-CO (principio VIII): miles con punto, decimales con coma, hora de Colombia. */

export const TIME_ZONE = "America/Bogota";

const numberFmt = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 1 });
const intFmt = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });

export function formatNumber(value: number, decimals?: number): string {
  if (decimals === undefined) return numberFmt.format(value);
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatInt(value: number): string {
  return intFmt.format(value);
}

export function formatPercent(value: number, decimals = 1): string {
  return `${formatNumber(value, decimals)} %`;
}

export function formatDateTime(iso: string | Date): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat("es-CO", {
    timeZone: TIME_ZONE,
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(date);
}

export function formatTime(iso: string | Date): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat("es-CO", {
    timeZone: TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).format(date);
}
