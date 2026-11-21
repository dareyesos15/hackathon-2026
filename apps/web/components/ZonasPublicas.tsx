"use client";
/**
 * Zonas inseguras en el tablero público (solo lectura): edificios acordonados vigilados por el
 * dispositivo UNAL de la patente NC2025/0015763 y si tienen una alarma abierta. Sin acciones ni
 * credenciales RFID: atender alarmas y simular lecturas queda en el tablero del PMU.
 */
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { simulado } from "@/lib/env";
import { formatInt } from "@/lib/format";
import type { ZoneSensorOut } from "@/lib/zones";

interface Props {
  sensors: ZoneSensorOut[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

export function ZonasPublicas({ sensors, selectedId, onSelect }: Props) {
  const alarms = sensors.reduce((n, s) => n + s.open_alarms, 0);
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="font-semibold">Zonas inseguras</h2>
        <EtiquetaSimulado />
      </div>
      <p className="text-xs leading-snug text-tinta-suave">
        Edificios acordonados con el dispositivo UNAL de monitoreo de zonas inseguras (patente
        NC2025/0015763): detecta a quien entra sin credencial de rescatista. No entre a estas zonas
        {simulado(" · lecturas SIMULADAS")}.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-papel p-2">
          <p className="text-xs text-tinta-suave">Zonas vigiladas</p>
          <p className="text-xl font-bold tabular-nums">{formatInt(sensors.length)}</p>
        </div>
        <div className="rounded-lg bg-papel p-2">
          <p className="text-xs text-tinta-suave">Alarmas abiertas</p>
          <p className={`text-xl font-bold tabular-nums ${alarms > 0 ? "text-senal" : ""}`}>
            {formatInt(alarms)}
          </p>
        </div>
      </div>
      <ul className="flex flex-col divide-y divide-linea">
        {sensors.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => onSelect(selectedId === s.id ? null : s.id)}
              className={`flex w-full items-center gap-2 py-1.5 text-left text-xs ${
                selectedId === s.id ? "font-semibold" : ""
              }`}
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: s.open_alarms > 0 ? "#d21f2b" : "#0e7490" }}
              />
              <span className="flex-1 truncate">{s.label}</span>
              {s.open_alarms > 0 ? (
                <span className="rounded bg-senal px-1 text-[10px] text-white">
                  Intrusión detectada
                </span>
              ) : (
                <span className="text-tinta-suave">Sin novedad</span>
              )}
            </button>
          </li>
        ))}
        {sensors.length === 0 && (
          <li className="py-2 text-xs text-tinta-suave">No hay zonas vigiladas.</li>
        )}
      </ul>
    </section>
  );
}
