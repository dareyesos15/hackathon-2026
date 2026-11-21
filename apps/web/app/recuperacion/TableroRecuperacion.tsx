"use client";
/**
 * Tablero de recuperación unificado: los 10 indispensables para el COE, las necesidades que hoy
 * exigen acción y el ciclo económico en 5 etapas.
 *
 * Regla de oro: cada cifra lleva el nombre del diccionario de indicadores, fuente, versión y hora
 * de corte (componente `Cifra`), y se cuentan predios únicos, no visitas.
 */
import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import { Cifra } from "@/components/Cifra";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { formatDate, formatDateTime, formatInt, formatPercent } from "@/lib/format";
import {
  CHANNEL_LABEL,
  COLOR_HEX,
  NEED_SEVERITY,
  SERVICE_LABEL,
  STAGE_STATUS,
  type BarrioRecovery,
  type CurvePoint,
  type DashFigure,
  type DashIndicator,
  type Need,
  type RecoveryDashboard,
  type ServiceKey,
  type Stage,
} from "@/lib/recovery";
import { Card } from "./ui";

const REFRESH_MS = 10_000;

function Figura({ f }: { f: DashFigure }) {
  return (
    <Cifra
      etiqueta={f.label}
      valor={f.value ?? null}
      unidad={f.unit}
      fuente={f.source}
      version={f.version}
      corte={f.cutoff_at}
      simulado={f.simulated}
      meta={f.target ?? undefined}
      estado={f.state}
    />
  );
}

function Figuras({ figures, cols = 4 }: { figures: DashFigure[]; cols?: 2 | 3 | 4 }) {
  const grid = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-2 lg:grid-cols-4" }[
    cols
  ];
  return (
    <div className={`grid grid-cols-1 gap-3 ${grid}`}>
      {figures.map((f) => (
        <Figura key={f.key} f={f} />
      ))}
    </div>
  );
}

function Indicador({
  ind,
  cols,
  children,
}: {
  ind: DashIndicator;
  cols?: 2 | 3 | 4;
  children?: ReactNode;
}) {
  return (
    <Card
      title={`${ind.number}. ${ind.title}`}
      extra={<span className="text-xs text-tinta-suave">Fuente: {ind.source}</span>}
    >
      <Figuras figures={ind.figures} cols={cols} />
      {children}
    </Card>
  );
}

// --------------------------------------------------------------------------- necesidades

function Necesidades({ needs }: { needs: Need[] }) {
  return (
    <Card title="Lo que se necesita hoy">
      {needs.length === 0 ? (
        <p className="text-sm text-tinta-suave">
          Sin necesidades abiertas con los datos de este corte.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {needs.map((n) => {
            const sev = NEED_SEVERITY[n.severity];
            return (
              <li
                key={n.key}
                className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded border px-3 py-2 ${sev.cls}`}
              >
                <span className="font-display text-2xl font-semibold tabular-nums">
                  {formatInt(n.value)}
                </span>
                <span className="font-semibold">{n.title}</span>
                <span className="rounded-sm border border-current px-1.5 text-[11px] font-bold uppercase">
                  {sev.label}
                </span>
                <span className="basis-full text-sm opacity-90">{n.detail}</span>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

// --------------------------------------------------------------------------- curva del índice

const W = 960;
const H = 260;
const M = { l: 40, r: 16, t: 14, b: 28 };

function CurvaIndice({ points, day }: { points: CurvePoint[]; day: number }) {
  const [hover, setHover] = useState<CurvePoint | null>(null);
  if (points.length === 0) return null;
  const xMax = Math.max(90, day);
  const x = (d: number) => M.l + (d / xMax) * (W - M.l - M.r);
  const y = (v: number) => M.t + (1 - v / 100) * (H - M.t - M.b);
  const history = points.filter((p) => p.simulated);
  const today = points.find((p) => !p.simulated);
  const path = history.map((p, i) => `${i ? "L" : "M"}${x(p.day)},${y(p.value)}`).join(" ");
  const last = history.at(-1);

  function onMove(e: MouseEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    const d = ((((e.clientX - box.left) / box.width) * W - M.l) / (W - M.l - M.r)) * xMax;
    const nearest = points.reduce((a, b) => (Math.abs(b.day - d) < Math.abs(a.day - d) ? b : a));
    setHover(nearest);
  }

  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="text-xs text-tinta-suave">
        Índice de la ciudad, día 0 a {xMax}. La línea continua es el histórico SIMULADO; el punto es
        el valor de hoy calculado en vivo.
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Curva del índice de recuperación por día desde el sismo"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="#e4dcdb" strokeWidth={1} />
            <text x={M.l - 6} y={y(v) + 4} textAnchor="end" fontSize={11} fill="#6b5c5f">
              {v} %
            </text>
          </g>
        ))}
        {Array.from({ length: Math.floor(xMax / 15) + 1 }, (_, i) => i * 15).map((d) => (
          <text key={d} x={x(d)} y={H - 8} textAnchor="middle" fontSize={11} fill="#6b5c5f">
            día {d}
          </text>
        ))}
        <path d={path} fill="none" stroke="#5c0f1b" strokeWidth={2} strokeLinejoin="round" />
        {today && last && (
          <line
            x1={x(last.day)}
            y1={y(last.value)}
            x2={x(today.day)}
            y2={y(today.value)}
            stroke="#5c0f1b"
            strokeWidth={2}
            strokeDasharray="4 4"
          />
        )}
        {today && (
          <g>
            <circle
              cx={x(today.day)}
              cy={y(today.value)}
              r={6}
              fill="#5c0f1b"
              stroke="#fff"
              strokeWidth={2}
            />
            <text
              x={x(today.day) - 10}
              y={y(today.value) - 10}
              textAnchor="end"
              fontSize={12}
              fontWeight={600}
              fill="#231a1c"
            >
              Hoy · {formatPercent(today.value)}
            </text>
          </g>
        )}
        {hover && (
          <g pointerEvents="none">
            <line
              x1={x(hover.day)}
              x2={x(hover.day)}
              y1={M.t}
              y2={H - M.b}
              stroke="#6b5c5f"
              strokeWidth={1}
            />
            <circle cx={x(hover.day)} cy={y(hover.value)} r={4} fill="#5c0f1b" />
            <rect
              x={Math.min(x(hover.day) + 8, W - 170)}
              y={M.t}
              width={160}
              height={22}
              rx={3}
              fill="#fff"
              stroke="#e4dcdb"
            />
            <text
              x={Math.min(x(hover.day) + 16, W - 162)}
              y={M.t + 15}
              fontSize={12}
              fill="#231a1c"
            >
              Día {hover.day} · {formatPercent(hover.value)}
              {hover.simulated ? " · simulado" : " · hoy"}
            </text>
          </g>
        )}
      </svg>
    </figure>
  );
}

function Componentes({ c }: { c: Record<string, number | null> }) {
  const names: [string, string][] = [
    ["habitabilidad", "Habitabilidad (3)"],
    ["servicios", "Servicios (6)"],
    ["familias", "Familias en casa (7)"],
    ["economia", "Negocios reabiertos (9)"],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
      {names.map(([k, label]) => (
        <div key={k} className="flex flex-col">
          <dt className="text-xs text-tinta-suave">{label}</dt>
          <dd className="font-semibold tabular-nums">
            {c[k] === null || c[k] === undefined ? "sin datos" : formatPercent(c[k])}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// --------------------------------------------------------------------------- barrios

function peorServicio(b: BarrioRecovery): [ServiceKey, number] | null {
  const entries = Object.entries(b.services) as [ServiceKey, number][];
  if (entries.length === 0) return null;
  return entries.reduce((a, e) => (e[1] < a[1] ? e : a));
}

function Barrios({ barrios }: { barrios: BarrioRecovery[] }) {
  const [all, setAll] = useState(false);
  const sorted = [...barrios].sort((a, b) => (a.index ?? 101) - (b.index ?? 101));
  const rows = all ? sorted : sorted.slice(0, 10);
  return (
    <Card
      title="Recuperación por barrio"
      extra={
        <button
          type="button"
          onClick={() => setAll(!all)}
          className="rounded border border-linea px-3 py-1 text-sm"
        >
          {all ? "Ver los 10 más rezagados" : `Ver los ${barrios.length} barrios`}
        </button>
      }
    >
      <p className="text-xs text-tinta-suave">
        Ordenados del más rezagado al más recuperado. Semáforo NSR-10 por predio único; el servicio
        más bajo y su fecha estimada vienen de las empresas de servicios.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] text-left text-sm">
          <thead className="text-xs text-tinta-suave">
            <tr className="border-b border-linea">
              <th className="py-1 pr-3 font-normal">Barrio</th>
              <th className="py-1 pr-3 text-right font-normal">Índice</th>
              <th className="py-1 pr-3 font-normal">Verde · Amarillo · Rojo · Colapso</th>
              <th className="py-1 pr-3 text-right font-normal">Pendientes</th>
              <th className="py-1 pr-3 font-normal">Servicio más bajo</th>
              <th className="py-1 font-normal">Fecha estimada</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-linea">
            {rows.map((b) => {
              const worst = peorServicio(b);
              return (
                <tr key={b.barrio}>
                  <td className="py-1.5 pr-3">
                    <span className="font-medium">{b.barrio}</span>{" "}
                    <span className="text-xs text-tinta-suave">{b.comuna}</span>
                  </td>
                  <td className="whitespace-nowrap py-1.5 pr-3 text-right font-semibold tabular-nums">
                    {b.index === null || b.index === undefined ? "—" : formatPercent(b.index)}
                  </td>
                  <td className="py-1.5 pr-3 tabular-nums">
                    <span className="inline-flex items-center gap-2">
                      {(
                        [
                          ["verde", b.verde],
                          ["amarillo", b.amarillo],
                          ["rojo", b.rojo],
                        ] as const
                      ).map(([c, n]) => (
                        <span key={c} className="inline-flex items-center gap-1">
                          <span
                            aria-hidden
                            className="inline-block h-2.5 w-2.5 rounded-full"
                            style={{ background: COLOR_HEX[c] }}
                          />
                          {n}
                        </span>
                      ))}
                      <span className="inline-flex items-center gap-1">
                        <span aria-hidden className="inline-block h-2.5 w-2.5 bg-tinta" />
                        {b.colapso}
                      </span>
                    </span>
                  </td>
                  <td
                    className={`py-1.5 pr-3 text-right tabular-nums ${b.pending > 0 ? "font-semibold text-senal" : ""}`}
                  >
                    {formatInt(b.pending)}
                  </td>
                  <td className="py-1.5 pr-3">
                    {worst ? (
                      <span className={worst[1] < 80 ? "font-semibold text-senal" : ""}>
                        {SERVICE_LABEL[worst[0]]} {worst[1]} %
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-1.5 text-xs text-tinta-suave">
                    {b.services_eta ? formatDate(b.services_eta) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------------- barras simples

function Barras({ items }: { items: { label: string; value: number; text: string }[] }) {
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[9rem_1fr_auto] items-center gap-2">
          <span className="text-tinta-suave">{i.label}</span>
          <span className="h-2.5 overflow-hidden rounded-sm bg-linea">
            <span
              className="block h-full rounded-sm bg-tinta"
              style={{ width: `${(i.value / max) * 100}%` }}
            />
          </span>
          <span className="tabular-nums">{i.text}</span>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------- ciclo económico

function Ciclo({ stages, day }: { stages: Stage[]; day: number }) {
  const xMax = Math.max(90, day);
  const pos = (d: number) => `${(Math.min(d, xMax) / xMax) * 100}%`;
  return (
    <div className="flex flex-col gap-4">
      <Card title="Línea de tiempo">
        <p className="text-xs text-tinta-suave">
          Cada etapa con su ventana de días y su semáforo: a tiempo, con retraso o estancada según
          el avance esperado para el día de hoy.
        </p>
        <div className="relative flex flex-col gap-3">
          {stages.map((s) => {
            const st = STAGE_STATUS[s.status];
            return (
              <div key={s.number} className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-x-2 text-sm">
                  <span>
                    <span className="text-tinta-suave">{s.number}.</span> {s.title}
                  </span>
                  <span className="relative z-10 ml-auto flex items-center gap-1.5 bg-white pl-1 text-xs">
                    <span
                      aria-hidden
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: st.hex }}
                    />
                    <span className="font-semibold">{st.label}</span>
                    {s.progress_pct !== null && s.progress_pct !== undefined && (
                      <span className="text-tinta-suave">
                        · avance {formatPercent(s.progress_pct, 0)}
                      </span>
                    )}
                  </span>
                </div>
                <span className="relative h-3 rounded-sm bg-linea/60">
                  <span
                    className="absolute top-0 h-full rounded-sm"
                    style={{
                      left: pos(s.start_day),
                      width: `calc(${pos(s.end_day)} - ${pos(s.start_day)})`,
                      background: st.hex,
                    }}
                  />
                </span>
              </div>
            );
          })}
          <span
            aria-hidden
            className="pointer-events-none absolute top-0 bottom-5 w-0.5 bg-sangre"
            style={{ left: pos(day) }}
          />
          <div className="relative h-4 text-[11px] text-tinta-suave">
            {[0, 15, 30, 45, 60, 75, 90].map((d) => (
              <span key={d} className="absolute -translate-x-1/2" style={{ left: pos(d) }}>
                {d}
              </span>
            ))}
          </div>
          <p className="text-right text-xs text-tinta-suave">
            Días desde el sismo · la línea vertical marca hoy (día {day})
          </p>
        </div>
      </Card>
      {stages.map((s) => {
        const st = STAGE_STATUS[s.status];
        return (
          <Card
            key={s.number}
            title={`Etapa ${s.number}. ${s.title} (días ${s.start_day} a ${s.end_day})`}
            extra={
              <span className="flex items-center gap-1.5 text-sm">
                <span
                  aria-hidden
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ background: st.hex }}
                />
                <span className="font-semibold">{st.label}</span>
              </span>
            }
          >
            <p className="font-display text-base italic text-tinta-suave">{s.question}</p>
            <Figuras figures={s.figures} cols={s.figures.length >= 4 ? 4 : 3} />
          </Card>
        );
      })}
    </div>
  );
}

// --------------------------------------------------------------------------- tablero

export function TableroRecuperacion() {
  const [data, setData] = useState<RecoveryDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const loop = () =>
      api
        .GET("/api/v1/recovery/dashboard")
        .then(({ data: d, error: e }) => {
          if (!active) return;
          if (d) {
            setData(d);
            setError(null);
          } else if (e) setError("No se pudo cargar el tablero de recuperación.");
        })
        .catch(() => active && setError("Sin conexión con la API: se muestra el último corte."))
        .finally(() => {
          if (active) timer = setTimeout(loop, REFRESH_MS);
        });
    void loop();
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (!data) {
    return <p className="text-sm text-tinta-suave">{error ?? "Cargando tablero…"}</p>;
  }

  const ind = Object.fromEntries(data.indicators.map((i) => [i.number, i])) as Record<
    number,
    DashIndicator
  >;
  const families = ind[1].figures.find((f) => f.key === "familias_unicas")?.value ?? 0;
  const funnel = ind[10].figures.filter((f) =>
    ["comprometido", "contratado", "pagado", "verificado"].includes(f.key),
  );
  const funnelBase = funnel[0]?.value ?? 0;

  return (
    <div className="flex flex-col gap-5">
      {error && (
        <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {error}
        </p>
      )}
      <section className="grid gap-4 rounded-md bg-sangre p-5 text-white sm:grid-cols-3">
        <div>
          <p className="text-sm text-white/75">Índice de recuperación de la ciudad</p>
          <p className="mt-1 font-display text-5xl font-semibold leading-none tabular-nums">
            {data.index === null || data.index === undefined ? "—" : formatPercent(data.index)}
          </p>
        </div>
        <div>
          <p className="text-sm text-white/75">Días desde el sismo del 10 ago 2026</p>
          <p className="mt-1 font-display text-5xl font-semibold leading-none tabular-nums">
            {formatInt(data.day)}
          </p>
        </div>
        <div>
          <p className="text-sm text-white/75">Familias damnificadas únicas</p>
          <p className="mt-1 font-display text-5xl font-semibold leading-none tabular-nums">
            {formatInt(families ?? 0)}
          </p>
        </div>
        <p className="flex flex-wrap items-center gap-2 text-xs text-white/70 sm:col-span-3">
          <EtiquetaSimulado sobreOscuro /> Corte {formatDateTime(data.cutoff_at)} · predios únicos,
          no visitas
        </p>
      </section>

      <Necesidades needs={data.needs} />

      <h2 className="font-display text-xl font-semibold">Encabezado</h2>
      <Indicador ind={ind[1]} cols={3} />
      <Indicador ind={ind[2]} cols={3} />
      <Indicador ind={ind[3]} />
      <Indicador ind={ind[4]} cols={2}>
        <Componentes c={data.index_components} />
        <CurvaIndice points={data.index_curve} day={data.day} />
      </Indicador>
      <Indicador ind={ind[5]} />
      <Barrios barrios={data.barrios} />

      <h2 className="font-display text-xl font-semibold">Operación</h2>
      <Indicador ind={ind[6]} cols={3} />
      <Indicador ind={ind[7]} />
      <Indicador ind={ind[8]} cols={3}>
        {data.channels.length > 0 && (
          <div className="flex flex-col gap-1">
            <p className="text-xs text-tinta-suave">Reportes por canal</p>
            <Barras
              items={data.channels.map((c) => ({
                label: CHANNEL_LABEL[c.channel] ?? c.channel,
                value: c.count,
                text: formatInt(c.count),
              }))}
            />
          </div>
        )}
      </Indicador>

      <h2 className="font-display text-xl font-semibold">Economía</h2>
      <Indicador ind={ind[9]}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-tinta-suave">
              <tr className="border-b border-linea">
                <th className="py-1 pr-3 font-normal">Comuna</th>
                <th className="py-1 pr-3 text-right font-normal">Negocios reabiertos</th>
                <th className="py-1 text-right font-normal">Empleos recuperados</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-linea">
              {data.economy.map((e) => (
                <tr key={e.comuna}>
                  <td className="py-1.5 pr-3">{e.comuna}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {formatInt(e.businesses_reopened)} de {formatInt(e.businesses_closed)}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatInt(e.jobs_recovered)} de {formatInt(e.jobs_lost)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Indicador>
      <Indicador ind={ind[10]}>
        <div className="flex flex-col gap-1">
          <p className="text-xs text-tinta-suave">
            Embudo: comprometido → contratado → pagado → resultado verificado
          </p>
          <Barras
            items={funnel.map((f) => ({
              label: f.label,
              value: f.value ?? 0,
              text: funnelBase
                ? `${formatPercent(((f.value ?? 0) / funnelBase) * 100, 0)} del comprometido`
                : "—",
            }))}
          />
        </div>
      </Indicador>

      <h2 className="font-display text-xl font-semibold">Ciclo económico de la recuperación</h2>
      <Ciclo stages={data.stages} day={data.day} />
    </div>
  );
}
