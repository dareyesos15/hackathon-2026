import { EtiquetaSimulado } from "./EtiquetaSimulado";
import { DEMO_MODE } from "@/lib/env";
import { formatCop, formatDateTime, formatInt, formatNumber, formatPercent } from "@/lib/format";

/**
 * Toda cifra visible exige fuente, versión y fecha de corte (principio V).
 * Si falta alguno, TypeScript no compila.
 */
export interface CifraProps {
  etiqueta: string;
  valor: number | null;
  unidad: "%" | "conteo" | "min" | "ms" | "dias" | "cop" | "mm" | "magnitud";
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
    case "dias":
      return `${formatInt(valor)} ${valor === 1 ? "día" : "días"}`;
    case "cop":
      return formatCop(valor);
    case "mm":
      return `${formatNumber(valor, 1)} mm`;
    case "magnitud":
      return `M ${formatNumber(valor, 1)}`;
  }
}

/** El rojo solo aparece cuando la cifra exige atención: el estado no es decoración. */
const ESTADO: Record<NonNullable<CifraProps["estado"]>, { caja: string; valor: string }> = {
  ok: { caja: "border-linea bg-white", valor: "text-tinta" },
  alerta: { caja: "border-senal bg-senal-fondo", valor: "text-senal" },
  neutral: { caja: "border-linea bg-white", valor: "text-tinta" },
};

export function Cifra(props: CifraProps) {
  const { etiqueta, valor, unidad, fuente, version, corte, simulado, meta, estado } = props;
  const tono = ESTADO[estado ?? "neutral"];
  return (
    <div className={`rounded-md border p-3 ${tono.caja}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm leading-tight text-tinta-suave">{etiqueta}</p>
        {simulado && <EtiquetaSimulado />}
      </div>
      <p
        className={`mt-1 font-display text-4xl font-semibold leading-none tabular-nums ${tono.valor}`}
      >
        {valor === null ? "—" : formatValue(valor, unidad)}
        {estado === "ok" && (
          <span className="ml-2 align-middle text-sm font-medium text-verificado">cumple</span>
        )}
      </p>
      {meta && <p className="mt-1 text-xs text-tinta-suave">Meta: {meta}</p>}
      {DEMO_MODE && (
        <p className="mt-1 text-[10px] leading-tight text-tinta-suave">
          Fuente: {fuente} · v{version} · corte {formatDateTime(corte)}
        </p>
      )}
    </div>
  );
}
