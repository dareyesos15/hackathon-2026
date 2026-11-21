/** Piezas visuales compartidas por las pestañas de recuperación. */
import type { ReactNode } from "react";

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
