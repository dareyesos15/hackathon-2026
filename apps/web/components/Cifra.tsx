import { formatDateTime, formatInt, formatNumber, formatPercent } from "@/lib/format";
import { EtiquetaSimulado } from "./EtiquetaSimulado";

/**
 * Toda cifra visible exige fuente, versión y fecha de corte (principio V).
 * Si falta alguno, TypeScript no compila.
 */
export interface CifraProps {
  etiqueta: string;
  valor: number | null;
  unidad: "%" | "conteo" | "min" | "ms";
  fuente: string;
  version: number | string;
  corte: string;
  simulado?: boolean;
  meta?: string;
  estado?: "ok" | "alerta" | "neutral";
}

function formatValue(valor: number, unidad: CifraProps["unidad"]): string {
  switch (unidad) {
    case "%":
      return formatPercent(valor);
    case "conteo":
      return formatInt(valor);
    case "min":
      return `${formatNumber(valor, 0)} min`;
    case "ms":
      return `${formatInt(valor)} ms`;
  }
}

const ESTADO: Record<NonNullable<CifraProps["estado"]>, string> = {
  ok: "border-emerald-500",
  alerta: "border-red-500",
  neutral: "border-slate-300",
};

export function Cifra(props: CifraProps) {
  const { etiqueta, valor, unidad, fuente, version, corte, simulado, meta, estado } = props;
  return (
    <div className={`rounded-lg border-l-4 bg-white p-3 shadow-sm ${ESTADO[estado ?? "neutral"]}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-slate-600">{etiqueta}</p>
        {simulado && <EtiquetaSimulado />}
      </div>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">
        {valor === null ? "—" : formatValue(valor, unidad)}
      </p>
      {meta && <p className="text-[11px] text-slate-500">Meta: {meta}</p>}
      <p className="mt-1 text-[10px] leading-tight text-slate-500">
        Fuente: {fuente} · v{version} · corte {formatDateTime(corte)}
      </p>
    </div>
  );
}
