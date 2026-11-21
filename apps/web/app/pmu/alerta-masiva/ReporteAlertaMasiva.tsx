"use client";
/**
 * Reporte de una alerta masiva: problemas atendidos, su trazabilidad (bitácora y despachos) y
 * tiempos de solución. Final cuando la alerta se resolvió (todos sus incidentes cerrados);
 * preliminar al corte mientras siga activa. Sin datos personales (Ley 1581).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { formatDateTime, formatInt } from "@/lib/format";
import {
  CATEGORY_LABEL,
  CHANNEL_LABEL,
  STATUS_LABEL,
  TRIAGE_COLOR,
  TRIAGE_LABEL,
  TRIAGE_ORDER,
  type Category,
  type Channel,
  type IncidentStatus,
  type TriageLevel,
} from "@/lib/labels";
import {
  MASS_EVENT_LABEL,
  ROLE_LABEL,
  TRACE_ACTION_LABEL,
  formatMinutes,
  type MassAlertOut,
  type MassAlertReportBody,
  type Problem,
  type TimeStats,
} from "@/lib/massAlerts";
import { getSession } from "@/lib/session";

const REFRESH_MS = 10000;

const cat = (c: string) => CATEGORY_LABEL[c as Category] ?? c;
const tri = (t: string) => TRIAGE_LABEL[t as TriageLevel] ?? t;
const st = (s: string) => STATUS_LABEL[s as IncidentStatus] ?? s;
const dt = (iso: string | null) => (iso ? formatDateTime(iso) : "—");

function Tile({ label, value, tone }: { label: string; value: number; tone?: "alerta" | "ok" }) {
  const color = tone === "alerta" ? "text-senal" : tone === "ok" ? "text-verificado" : "";
  return (
    <div className="rounded-md border border-linea bg-white px-3 py-2">
      <div className="text-xs text-tinta-suave">{label}</div>
      <div className={`font-display text-3xl font-semibold tabular-nums ${color}`}>
        {formatInt(value)}
      </div>
    </div>
  );
}

function Distribucion({
  title,
  data,
  label,
}: {
  title: string;
  data: Record<string, number>;
  label: (k: string) => string;
}) {
  const entries = Object.entries(data);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <section className="rounded-md border border-linea bg-white p-3 break-inside-avoid">
      <h3 className="mb-2 font-display text-lg font-semibold">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-tinta-suave">Sin datos.</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {entries.slice(0, 12).map(([k, v]) => (
            <li key={k} className="grid grid-cols-[minmax(0,10rem)_1fr_2.5rem] items-center gap-2">
              <span className="truncate" title={label(k)}>
                {label(k)}
              </span>
              <span className="h-2 rounded-sm bg-linea">
                <span
                  className="block h-2 rounded-sm bg-sangre"
                  style={{ width: `${(v / max) * 100}%` }}
                />
              </span>
              <span className="text-right tabular-nums">{formatInt(v)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TiemposRow({ label, s }: { label: string; s: TimeStats }) {
  return (
    <tr className="border-t border-linea">
      <th className="py-1.5 pr-3 text-left font-medium">{label}</th>
      <td className="px-2 text-right tabular-nums">{formatMinutes(s.promedio)}</td>
      <td className="px-2 text-right tabular-nums">{formatMinutes(s.mediana)}</td>
      <td className="px-2 text-right tabular-nums">{formatMinutes(s.maximo)}</td>
      <td className="pl-2 text-right tabular-nums text-tinta-suave">{s.n}</td>
    </tr>
  );
}

function TriajeChip({ level }: { level: string }) {
  return (
    <span
      className="inline-block rounded-sm px-1.5 py-0.5 text-xs font-bold text-white"
      style={{ background: TRIAGE_COLOR[level as TriageLevel] ?? "#6e7c8c" }}
    >
      {tri(level)}
    </span>
  );
}

function Trazabilidad({ p }: { p: Problem }) {
  return (
    <div className="grid gap-4 bg-papel px-3 py-3 md:grid-cols-2">
      <div>
        <h4 className="mb-1 text-sm font-semibold">Bitácora</h4>
        <ol className="flex flex-col gap-1 border-l-2 border-linea pl-3 text-xs">
          {p.bitacora.map((e, i) => (
            <li key={i}>
              <span className="tabular-nums text-tinta-suave">{dt(e.at)}</span> ·{" "}
              <span className="font-medium">{TRACE_ACTION_LABEL[e.accion] ?? e.accion}</span> ·{" "}
              {ROLE_LABEL[e.rol] ?? e.rol}
              {e.reportes > 1 && <span className="text-tinta-suave"> ({e.reportes} reportes)</span>}
              {e.nota && <span className="block italic text-tinta-suave">“{e.nota}”</span>}
            </li>
          ))}
        </ol>
      </div>
      <div>
        <h4 className="mb-1 text-sm font-semibold">Despachos</h4>
        {p.despachos.length === 0 ? (
          <p className="text-xs text-tinta-suave">Sin despachos.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-xs">
            {p.despachos.map((d, i) => (
              <li key={i} className="rounded border border-linea bg-white px-2 py-1">
                <span className="font-medium">{d.agencia_nombre}</span> · {d.recurso}
                {d.refuerzo && " · refuerzo"} · <span className="italic">{d.estado}</span>
                <span className="block text-tinta-suave">
                  Despachado {dt(d.creado_at)} · llegada {dt(d.llegada_at)} · cierre{" "}
                  {dt(d.cierre_at)} · {formatInt(d.distancia_m)} m
                </span>
              </li>
            ))}
          </ul>
        )}
        <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
          <dt className="text-tinta-suave">Registrado</dt>
          <dd>{dt(p.registrado_at)}</dd>
          <dt className="text-tinta-suave">Verificado</dt>
          <dd>{dt(p.verificado_at)}</dd>
          <dt className="text-tinta-suave">Primer despacho</dt>
          <dd>{dt(p.primer_despacho_at)}</dd>
          <dt className="text-tinta-suave">Primera llegada</dt>
          <dd>{dt(p.primera_llegada_at)}</dd>
          <dt className="text-tinta-suave">Cerrado</dt>
          <dd>{dt(p.cerrado_at)}</dd>
        </dl>
      </div>
    </div>
  );
}

function download(name: string, type: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function toCsv(report: MassAlertReportBody): string {
  const header = [
    "incidente",
    "categoria",
    "triaje",
    "riesgo_vital",
    "barrio",
    "manzana",
    "estado_final",
    "reportes",
    "fuentes_independientes",
    "registrado_at",
    "verificado_at",
    "primer_despacho_at",
    "primera_llegada_at",
    "cerrado_at",
    "min_a_verificacion",
    "min_a_despacho",
    "min_a_llegada",
    "min_a_solucion",
    "agencias",
  ];
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows = report.problemas.map((p) =>
    [
      p.incident_id,
      p.categoria,
      p.triaje,
      p.riesgo_vital,
      p.barrio,
      p.manzana_id,
      p.estado_final,
      p.reportes,
      p.fuentes_independientes,
      p.registrado_at,
      p.verificado_at,
      p.primer_despacho_at,
      p.primera_llegada_at,
      p.cerrado_at,
      p.min_a_verificacion,
      p.min_a_despacho,
      p.min_a_llegada,
      p.min_a_solucion,
      Array.from(new Set(p.despachos.map((d) => d.agencia))).join(" "),
    ]
      .map(esc)
      .join(","),
  );
  return [header.join(","), ...rows].join("\n");
}

export default function ReporteAlertaMasiva() {
  const router = useRouter();
  const [session] = useState(getSession);
  const [id] = useState(() => new URLSearchParams(window.location.search).get("id"));
  const [alert, setAlert] = useState<MassAlertOut | null>(null);
  const [report, setReport] = useState<MassAlertReportBody | null>(null);
  const [error, setError] = useState<string | null>(null);
  const allowed = session?.role === "pmu";

  useEffect(() => {
    if (!allowed) router.replace("/ingresar/");
  }, [allowed, router]);

  useEffect(() => {
    if (!allowed || !id) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const load = async () => {
      const { data, error: err } = await api.GET("/api/v1/mass-alerts/{mass_alert_id}/report", {
        params: { path: { mass_alert_id: id } },
      });
      if (!alive) return;
      if (data) {
        setAlert(data.mass_alert);
        const body = data.report as unknown as MassAlertReportBody;
        setReport(body);
        if (body.preliminar) timer = setTimeout(load, REFRESH_MS);
      } else {
        setError((err as { detail?: string } | undefined)?.detail ?? "No se pudo cargar");
      }
    };
    void load();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [allowed, id]);

  if (!allowed) return null;
  if (!id) return <p className="p-6">Falta el identificador de la alerta masiva.</p>;
  if (error) return <p className="p-6 text-senal">{error}</p>;
  if (!report || !alert) return <p className="p-6 text-sm text-tinta-suave">Cargando reporte…</p>;

  const r = report.resumen;
  const t = report.tiempos;
  const fileBase = `reporte-alerta-masiva-${report.alerta.inicio_at.slice(0, 10)}-${id.slice(0, 8)}`;

  return (
    <div className="min-h-screen bg-papel">
      <header className="flex flex-wrap items-center gap-3 bg-sangre px-4 py-3 text-white print:bg-white print:text-tinta">
        <h1 className="font-display text-2xl font-semibold leading-none">
          Dacora · Reporte de alerta masiva
        </h1>
        <EtiquetaSimulado sobreOscuro />
        <span
          className={`rounded-sm px-2 py-0.5 text-xs font-bold ${
            report.preliminar ? "bg-[#ffd27a] text-tinta" : "bg-white text-verificado"
          }`}
        >
          {report.preliminar ? "PRELIMINAR · alerta activa" : "FINAL · alerta resuelta"}
        </span>
        <nav className="ml-auto flex flex-wrap gap-2 text-sm print:hidden">
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded bg-white/15 px-2 py-1 hover:bg-white/25"
          >
            Imprimir / PDF
          </button>
          <button
            type="button"
            onClick={() => download(`${fileBase}.csv`, "text/csv;charset=utf-8", toCsv(report))}
            className="rounded bg-white/15 px-2 py-1 hover:bg-white/25"
          >
            Descargar CSV
          </button>
          <button
            type="button"
            onClick={() =>
              download(`${fileBase}.json`, "application/json", JSON.stringify(report, null, 2))
            }
            className="rounded bg-white/15 px-2 py-1 hover:bg-white/25"
          >
            Descargar JSON
          </button>
          <Link href="/pmu/" className="rounded bg-white px-2 py-1 font-bold text-sangre">
            Volver al tablero
          </Link>
        </nav>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4">
        <section className="rounded-md border border-linea bg-white p-4">
          <h2 className="font-display text-3xl font-semibold">{report.alerta.titulo}</h2>
          <p className="text-sm text-tinta-suave">
            {MASS_EVENT_LABEL[report.alerta.evento]} · toda la ciudad · activada por{" "}
            {ROLE_LABEL[report.alerta.creada_por] ?? report.alerta.creada_por}
          </p>
          {report.alerta.descripcion && <p className="mt-2">{report.alerta.descripcion}</p>}
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-4">
            <dt className="text-tinta-suave">Inicio</dt>
            <dd>{dt(report.alerta.inicio_at)}</dd>
            <dt className="text-tinta-suave">Fin</dt>
            <dd>{report.alerta.fin_at ? dt(report.alerta.fin_at) : "En curso"}</dd>
            <dt className="text-tinta-suave">Duración</dt>
            <dd>{formatMinutes(report.alerta.duracion_min)}</dd>
            <dt className="text-tinta-suave">Fecha de corte</dt>
            <dd>{dt(report.corte_at)}</dd>
          </dl>
          <p className="mt-2 text-xs text-tinta-suave">
            Fuente: {report.fuente} · generado {dt(report.generado_at)} · versión {report.version}.
            Los tiempos se miden desde que Dacora registra cada incidente.
          </p>
        </section>

        <section className="grid grid-cols-2 gap-2 md:grid-cols-6">
          <Tile label="Incidentes" value={r.incidentes} />
          <Tile label="Reportes" value={r.reportes} />
          <Tile label="Atendidos" value={r.atendidos} tone="ok" />
          <Tile label="Descartados" value={r.descartados} />
          <Tile label="Abiertos" value={r.abiertos} tone={r.abiertos > 0 ? "alerta" : "ok"} />
          <Tile label="Despachos" value={r.despachos} />
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-md border border-linea bg-white p-3 break-inside-avoid">
            <h3 className="mb-2 font-display text-lg font-semibold">Tiempos desde el registro</h3>
            <table className="w-full text-sm">
              <thead className="text-xs text-tinta-suave">
                <tr>
                  <th className="text-left font-normal">Hasta</th>
                  <th className="px-2 text-right font-normal">Promedio</th>
                  <th className="px-2 text-right font-normal">Mediana</th>
                  <th className="px-2 text-right font-normal">Máximo</th>
                  <th className="pl-2 text-right font-normal">n</th>
                </tr>
              </thead>
              <tbody>
                <TiemposRow label="Verificación" s={t.verificacion} />
                <TiemposRow label="Primer despacho" s={t.despacho} />
                <TiemposRow label="Llegada al sitio" s={t.llegada} />
                <TiemposRow label="Solución (cierre)" s={t.solucion} />
              </tbody>
            </table>
          </div>
          <div className="rounded-md border border-linea bg-white p-3 break-inside-avoid">
            <h3 className="mb-2 font-display text-lg font-semibold">
              Tiempo de solución por triaje
            </h3>
            <table className="w-full text-sm">
              <thead className="text-xs text-tinta-suave">
                <tr>
                  <th className="text-left font-normal">Nivel</th>
                  <th className="px-2 text-right font-normal">Promedio</th>
                  <th className="px-2 text-right font-normal">Mediana</th>
                  <th className="px-2 text-right font-normal">Máximo</th>
                  <th className="pl-2 text-right font-normal">n</th>
                </tr>
              </thead>
              <tbody>
                {TRIAGE_ORDER.filter((lvl) => t.solucion_por_triaje[lvl]).map((lvl) => (
                  <TiemposRow key={lvl} label={tri(lvl)} s={t.solucion_por_triaje[lvl]} />
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-tinta-suave">
              Riesgo vital: {formatInt(r.riesgo_vital)} incidentes.
            </p>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <Distribucion title="Problemas por categoría" data={r.por_categoria} label={cat} />
          <Distribucion title="Problemas por barrio" data={r.por_barrio} label={(k) => k} />
          <Distribucion
            title="Reportes por canal"
            data={r.por_canal}
            label={(k) => CHANNEL_LABEL[k as Channel] ?? k}
          />
          <Distribucion title="Despachos por agencia" data={r.por_agencia} label={(k) => k} />
        </section>

        <section className="rounded-md border border-linea bg-white">
          <h3 className="px-3 pt-3 font-display text-lg font-semibold">
            Problemas y trazabilidad ({formatInt(report.problemas.length)})
          </h3>
          <p className="px-3 pb-2 text-xs text-tinta-suave">
            Toque un problema para ver su bitácora (quién decidió qué y cuándo) y sus despachos.
          </p>
          <div className="overflow-x-auto">
            <div className="min-w-[760px]">
              <div className="grid grid-cols-[5rem_1fr_8rem_6rem_4rem_repeat(4,5.5rem)] gap-2 border-y border-linea bg-papel px-3 py-1.5 text-xs text-tinta-suave">
                <span>Triaje</span>
                <span>Problema</span>
                <span>Barrio</span>
                <span>Estado</span>
                <span className="text-right">Reportes</span>
                <span className="text-right">Verificación</span>
                <span className="text-right">Despacho</span>
                <span className="text-right">Llegada</span>
                <span className="text-right">Solución</span>
              </div>
              {report.problemas.map((p) => (
                <details key={p.incident_id} className="border-b border-linea break-inside-avoid">
                  <summary className="grid cursor-pointer grid-cols-[5rem_1fr_8rem_6rem_4rem_repeat(4,5.5rem)] items-center gap-2 px-3 py-1.5 text-sm hover:bg-papel">
                    <span>
                      <TriajeChip level={p.triaje} />
                    </span>
                    <span className="truncate">
                      {cat(p.categoria)}
                      {p.riesgo_vital && <span className="ml-1 text-xs text-senal">● vital</span>}
                    </span>
                    <span className="truncate">{p.barrio ?? "Sin ubicar"}</span>
                    <span>{st(p.estado_final)}</span>
                    <span className="text-right tabular-nums">{p.reportes}</span>
                    <span className="text-right tabular-nums">
                      {formatMinutes(p.min_a_verificacion)}
                    </span>
                    <span className="text-right tabular-nums">
                      {formatMinutes(p.min_a_despacho)}
                    </span>
                    <span className="text-right tabular-nums">
                      {formatMinutes(p.min_a_llegada)}
                    </span>
                    <span className="text-right font-medium tabular-nums">
                      {formatMinutes(p.min_a_solucion)}
                    </span>
                  </summary>
                  <Trazabilidad p={p} />
                </details>
              ))}
              {report.problemas.length === 0 && (
                <p className="px-3 py-4 text-sm text-tinta-suave">
                  Aún no hay incidentes en esta alerta.
                </p>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
