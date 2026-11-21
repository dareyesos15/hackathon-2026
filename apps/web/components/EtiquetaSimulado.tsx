/** Etiqueta visible para todo dato, capa o canal simulado (principio IV). */
export function EtiquetaSimulado({
  className = "",
  sobreOscuro = false,
}: {
  className?: string;
  /** true cuando va sobre la cabecera roja oscura. */
  sobreOscuro?: boolean;
}) {
  return (
    <span
      title="Datos sintéticos para la demo; no corresponden a personas ni hechos reales"
      className={`inline-flex items-center gap-1 rounded-sm border border-dashed border-current px-1.5 py-px text-[11px] font-bold ${sobreOscuro ? "text-[#ffd27a]" : "text-[#9a5b00]"} ${className}`}
    >
      <svg aria-hidden viewBox="0 0 12 12" className="h-2.5 w-2.5">
        <path d="M6 1 11 10H1Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      </svg>
      Simulado
    </span>
  );
}
