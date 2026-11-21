/** Piezas visuales compartidas por las pestañas de recuperación. */
import type { ReactNode } from "react";
import { COLOR_HEX, type InspectionColor, type ManzanaRef } from "@/lib/recovery";

export function Card({
  title,
  children,
  extra,
}: {
  title: string;
  children: ReactNode;
  extra?: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-lg bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        {extra}
      </div>
      {children}
    </section>
  );
}

export const input = "rounded border border-linea bg-white px-2 py-1.5 text-sm";
export const button =
  "rounded bg-sangre px-3 py-1.5 text-sm font-semibold text-white hover:bg-sangre-claro disabled:opacity-40";

export function Notice({ tone, children }: { tone: "ok" | "warn" | "error"; children: ReactNode }) {
  const cls = {
    ok: "bg-emerald-50 text-emerald-900 border-emerald-200",
    warn: "bg-amber-50 text-amber-900 border-amber-300",
    error: "bg-senal-fondo text-senal border-rose-200",
  }[tone];
  return <p className={`rounded border px-3 py-2 text-sm ${cls}`}>{children}</p>;
}

export function Dot({ color }: { color: InspectionColor }) {
  return (
    <span
      aria-hidden
      className="inline-block h-3 w-3 shrink-0 rounded-full"
      style={{ background: COLOR_HEX[color] }}
    />
  );
}

/** Selector de predio: código catastral o manzana + dirección. */
export function PropertyFields({
  manzanas,
  value,
  onChange,
  optional = false,
}: {
  manzanas: ManzanaRef[];
  value: { cadastral_code: string; manzana_id: string; address: string };
  onChange: (v: { cadastral_code: string; manzana_id: string; address: string }) => void;
  optional?: boolean;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      <label className="flex flex-col gap-1 text-xs text-tinta-suave">
        Código catastral {optional ? "(opcional)" : "(si lo tiene)"}
        <input
          className={input}
          value={value.cadastral_code}
          onChange={(e) => onChange({ ...value, cadastral_code: e.target.value })}
          placeholder="17001010200000123000"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-tinta-suave">
        Manzana
        <select
          className={input}
          value={value.manzana_id}
          onChange={(e) => onChange({ ...value, manzana_id: e.target.value })}
        >
          <option value="">Elija…</option>
          {manzanas.map((m) => (
            <option key={m.id} value={m.id}>
              {m.barrio} · {m.id}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-tinta-suave">
        Dirección del predio
        <input
          className={input}
          value={value.address}
          onChange={(e) => onChange({ ...value, address: e.target.value })}
          placeholder="Cra 23 # 45-10"
        />
      </label>
    </div>
  );
}

export const EMPTY_PROPERTY = { cadastral_code: "", manzana_id: "", address: "" };

export function propertyBody(p: typeof EMPTY_PROPERTY) {
  return {
    cadastral_code: p.cadastral_code.trim() || null,
    manzana_id: p.manzana_id || null,
    address: p.address.trim() || null,
  };
}
