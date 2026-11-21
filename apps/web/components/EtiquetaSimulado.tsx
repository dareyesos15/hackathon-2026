/** Etiqueta visible para todo dato, capa o canal simulado (principio IV). */
export function EtiquetaSimulado({ className = "" }: { className?: string }) {
  return (
    <span
      title="Datos sintéticos para la demo; no corresponden a personas ni hechos reales"
      className={`inline-flex items-center rounded border border-amber-500 bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-900 ${className}`}
    >
      Simulado
    </span>
  );
}
