"use client";
/** Matriz de triaje filtrable (FR-023): conteo por nivel + lista ordenada por nivel y antigüedad. */
import { useMemo, useState } from "react";
import { formatInt, formatTime } from "@/lib/format";
import { IconoCategoria } from "./IconoCategoria";
import {
  CATEGORY_LABEL,
  INCIDENT_DISPATCH_LABEL,
  STATUS_LABEL,
  TRIAGE_COLOR,
  TRIAGE_LABEL,
  TRIAGE_ORDER,
  TRUST_LABEL,
  TRUST_STYLE,
  type Category,
  type IncidentStatus,
  type IncidentSummary,
  type TriageLevel,
} from "@/lib/labels";

interface Props {
  incidents: IncidentSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

const RANK: Record<TriageLevel, number> = { critico: 0, alto: 1, medio: 2, bajo: 3 };
const OPEN_STATUSES: IncidentStatus[] = ["abierto", "en_revision"];

export function MatrizTriaje({ incidents, selectedId, onSelect }: Props) {
  const [triage, setTriage] = useState<TriageLevel | "todos">("todos");
  const [status, setStatus] = useState<IncidentStatus | "pendientes" | "todos">("pendientes");
  const [category, setCategory] = useState<Category | "todas">("todas");

  const counts = useMemo(() => {
    const c: Record<TriageLevel, { total: number; pendientes: number }> = {
      critico: { total: 0, pendientes: 0 },
      alto: { total: 0, pendientes: 0 },
      medio: { total: 0, pendientes: 0 },
      bajo: { total: 0, pendientes: 0 },
    };
    for (const i of incidents) {
      c[i.triage_level].total += 1;
      if (OPEN_STATUSES.includes(i.status)) c[i.triage_level].pendientes += 1;
    }
    return c;
  }, [incidents]);

  const rows = useMemo(
    () =>
      incidents
        .filter((i) => triage === "todos" || i.triage_level === triage)
        .filter((i) =>
          status === "todos"
            ? true
            : status === "pendientes"
              ? OPEN_STATUSES.includes(i.status)
              : i.status === status,
        )
        .filter((i) => category === "todas" || i.category === category)
        .sort(
          (a, b) =>
            RANK[a.triage_level] - RANK[b.triage_level] || a.first_seen.localeCompare(b.first_seen),
        ),
    [incidents, triage, status, category],
  );

  const categories = useMemo(
    () => Array.from(new Set(incidents.map((i) => i.category))).sort(),
    [incidents],
  );

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="grid grid-cols-4 overflow-hidden rounded-md border border-linea bg-white">
        {TRIAGE_ORDER.map((level) => {
          const active = triage === level;
          const urgent = level === "critico" && counts.critico.pendientes > 0;
          return (
            <button
              key={level}
              type="button"
              aria-pressed={active}
              onClick={() => setTriage(active ? "todos" : level)}
              className={`relative border-r border-linea p-2 pt-3 text-left last:border-r-0 ${
                urgent ? "bg-senal-fondo" : active ? "bg-papel" : "hover:bg-papel"
              } ${active ? "ring-2 ring-tinta ring-inset" : ""}`}
            >
              <span
                className={`absolute inset-x-0 top-0 ${active ? "h-2" : "h-1"}`}
                style={{ background: TRIAGE_COLOR[level] }}
              />
              <span className="block text-sm font-bold">{TRIAGE_LABEL[level]}</span>
              <span
                className={`block font-display text-3xl font-semibold leading-none tabular-nums ${
                  urgent ? "text-senal" : ""
                }`}
              >
                {formatInt(counts[level].pendientes)}
              </span>
              <span className="block text-[11px] text-tinta-suave">
                pendientes de {formatInt(counts[level].total)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <select
          aria-label="Estado"
          className="rounded border border-linea bg-white px-2 py-1"
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
        >
          <option value="pendientes">Pendientes de revisión</option>
          <option value="todos">Todos los estados</option>
          {(Object.keys(STATUS_LABEL) as IncidentStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
        <select
          aria-label="Categoría"
          className="rounded border border-linea bg-white px-2 py-1"
          value={category}
          onChange={(e) => setCategory(e.target.value as typeof category)}
        >
          <option value="todas">Todas las categorías</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {CATEGORY_LABEL[c]}
            </option>
          ))}
        </select>
        <span className="self-center text-tinta-suave">{formatInt(rows.length)} incidentes</span>
      </div>

      <ul className="flex-1 divide-y divide-linea overflow-y-auto rounded-md border border-linea bg-white">
        {rows.map((i) => (
          <li key={i.id}>
            <button
              type="button"
              onClick={() => onSelect(i.id)}
              className={`flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-papel ${
                i.id === selectedId ? "bg-senal-fondo" : ""
              } ${i.unattended ? "border-l-4 border-red-600 bg-red-50" : ""}`}
            >
              <IconoCategoria category={i.category} triage={i.triage_level} size={30} />
              <span className="flex-1">
                <span className="font-medium">
                  {CATEGORY_LABEL[i.category]}
                  {i.is_life_threat && (
                    <span className="ml-2 rounded-sm bg-senal px-1 py-px text-[11px] font-bold text-white">
                      Riesgo vital
                    </span>
                  )}
                </span>
                <span className="block text-xs text-tinta-suave">
                  {i.barrio ?? "Sin ubicación"} · {formatInt(i.report_count)} reportes ·{" "}
                  {formatInt(i.independent_sources)} fuentes · {formatTime(i.first_seen)}
                </span>
              </span>
              <span className="flex flex-col items-end gap-1">
                <span
                  className={`rounded border px-1.5 text-[10px] font-semibold ${TRUST_STYLE[i.trust_label]}`}
                >
                  {TRUST_LABEL[i.trust_label]} · {i.trust_score}
                </span>
                <span className="text-[10px] text-tinta-suave">{STATUS_LABEL[i.status]}</span>
                {i.dispatch_status !== "sin_despacho" ? (
                  <span className="rounded bg-violet-100 px-1.5 text-[10px] font-semibold text-violet-800">
                    {INCIDENT_DISPATCH_LABEL[i.dispatch_status]}
                    {i.assigned_agency ? ` · ${i.assigned_agency}` : ""}
                  </span>
                ) : (
                  i.unattended && (
                    <span className="rounded bg-red-600 px-1.5 text-[10px] font-bold text-white">
                      Sin despacho
                    </span>
                  )
                )}
              </span>
            </button>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="p-4 text-center text-sm text-tinta-suave">
            No hay incidentes con estos filtros.
          </li>
        )}
      </ul>
    </div>
  );
}
