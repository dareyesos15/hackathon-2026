"use client";
/**
 * Pestaña "Zonas" del tablero PMU (specs/004): sensor de zonas inseguras, patente UNAL
 * NC2025/0015763 (ultrasonido + infrarrojo en un cono configurable, RFID del personal
 * autorizado). Lecturas SIMULADAS: el simulador de la API y los botones de demo usan el mismo
 * punto de integración que el dispositivo real (`POST /sensors/zones/{id}/readings`).
 */
import { useEffect, useMemo, useState } from "react";
import { EtiquetaSimulado } from "@/components/EtiquetaSimulado";
import { api } from "@/lib/api/client";
import { simulado } from "@/lib/env";
import { formatTime } from "@/lib/format";
import { CATEGORY_LABEL, TRIAGE_LABEL, type IncidentSummary } from "@/lib/labels";
import {
  ZONE_DETECTOR_LABEL,
  ZONE_EVENT_LABEL,
  isAlarm,
  type ZoneEventOut,
  type ZoneSensorOut,
} from "@/lib/zones";

const STRUCTURAL = new Set(["personas_atrapadas", "colapso_estructura", "dano_estructural"]);

interface Props {
  sensors: ZoneSensorOut[];
  revision: number;
  incidents: IncidentSummary[];
  selectedSensorId: string | null;
  onSelectSensor: (id: string | null) => void;
  onOpenIncident: (id: string) => void;
}

function EventoLinea({ e, onAck }: { e: ZoneEventOut; onAck?: () => void }) {
  const alarm = isAlarm(e);
  return (
    <li
      className={`flex flex-col gap-0.5 rounded border px-2 py-1.5 text-xs ${
        alarm
          ? "border-rose-300 bg-senal-fondo"
          : e.kind === "acceso_autorizado"
            ? "border-emerald-200 bg-emerald-50"
            : "border-linea bg-white"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold">{ZONE_EVENT_LABEL[e.kind]}</span>
        <span className="text-tinta-suave">
          {e.sensor_code} · {formatTime(e.at)}
        </span>
        {onAck && alarm && (
          <button
            type="button"
            onClick={onAck}
            className="ml-auto rounded bg-sangre px-2 py-0.5 text-[11px] font-semibold text-white"
          >
            Atender
          </button>
        )}
        {e.acknowledged_at && (
          <span className="ml-auto text-tinta-suave">
            Atendida {formatTime(e.acknowledged_at)} · {e.acknowledged_by}
          </span>
        )}
      </div>
      <span className="text-tinta-suave">
        {e.sensor_label}
        {e.detector && ` · ${ZONE_DETECTOR_LABEL[e.detector]}`}
        {e.distance_m !== null && ` · a ${e.distance_m} m`}
        {e.rfid_tag
          ? ` · tarjeta ${e.rfid_tag}${e.authorized ? ` (${e.badge_agency})` : " no registrada"}`
          : e.detector
            ? " · sin tarjeta RFID"
            : ""}
        {e.kind === "bateria_baja" && ` · ${e.battery_pct} %`}
      </span>
    </li>
  );
}

export function PanelZonas({
  sensors,
  revision,
  incidents,
  selectedSensorId,
  onSelectSensor,
  onOpenIncident,
}: Props) {
  const [alarms, setAlarms] = useState<ZoneEventOut[]>([]);
  const [recent, setRecent] = useState<ZoneEventOut[]>([]);
  const [target, setTarget] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.GET("/api/v1/sensors/zones/events", { params: { query: { only_alarms: true } } }),
      api.GET("/api/v1/sensors/zones/events", { params: { query: { limit: 30 } } }),
    ]).then(([a, r]) => {
      if (!active) return;
      setAlarms(a.data?.items ?? []);
      setRecent(r.data?.items ?? []);
    });
    return () => {
      active = false;
    };
  }, [revision]);

  const structural = useMemo(
    () =>
      incidents
        .filter(
          (i) =>
            STRUCTURAL.has(i.category) &&
            i.lat !== null &&
            ["abierto", "en_revision", "verificado"].includes(i.status),
        )
        .sort((a, b) => b.report_count - a.report_count)
        .slice(0, 40),
    [incidents],
  );

  async function ack(id: string) {
    await api.POST("/api/v1/sensors/zones/events/{event_id}/ack", {
      params: { path: { event_id: id } },
    });
    setAlarms((prev) => prev.filter((e) => e.id !== id));
  }

  async function simulate(sensor: ZoneSensorOut, rescuer: boolean) {
    setMsg(null);
    const { data } = await api.POST("/api/v1/sensors/zones/{sensor_id}/readings", {
      params: { path: { sensor_id: sensor.id } },
      body: {
        ultrasonic_m: Math.round(sensor.range_m * 0.5 * 10) / 10,
        infrared: true,
        bearing_deg: 5,
        rfid_tag: rescuer ? "BOM-0101" : null,
        battery_pct: sensor.battery_pct,
        tamper: false,
      },
    });
    if (data && data.confirmed_incidents.length > 0) {
      setMsg(
        `La intrusión corrobora ${data.confirmed_incidents.length} incidente(s) cercano(s): +10 pts por sensor de campo.`,
      );
    }
  }

  async function install() {
    const incident = structural.find((i) => i.id === target);
    if (!incident) return;
    setMsg(null);
    const { data, error } = await api.POST("/api/v1/sensors/zones", {
      body: {
        label: `${CATEGORY_LABEL[incident.category]} · ${incident.barrio ?? "sin barrio"}`,
        incident_id: incident.id,
        heading_deg: 0,
        range_m: 12,
        half_angle_deg: 30,
      },
    });
    if (error || !data) {
      setMsg((error as { detail?: string } | undefined)?.detail ?? "No se pudo instalar");
      return;
    }
    setTarget("");
    onSelectSensor(data.id);
    setMsg(`Sensor ${data.code} instalado y armado en el incidente.`);
  }

  const selected = sensors.find((s) => s.id === selectedSensorId) ?? null;

  return (
    <div className="flex flex-col gap-3 text-sm">
      <section className="rounded-md bg-white p-3 shadow-sm">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-base font-semibold">Zonas inseguras</h2>
          <EtiquetaSimulado />
        </div>
        <p className="mt-1 text-xs leading-snug text-tinta-suave">
          Dispositivo UNAL de monitoreo de zonas inseguras (patente NC2025/0015763): sensores
          ultrasónico e infrarrojo vigilan un cono en edificios acordonados; el módulo RFID reconoce
          al personal autorizado y evita falsas alarmas. Una intrusión detectada por ambos sensores
          corrobora los incidentes estructurales a menos de 150 m{simulado(" · lecturas SIMULADAS")}
          .
        </p>
      </section>

      <section className="flex flex-col gap-2 rounded-md bg-white p-3 shadow-sm">
        <h3 className="font-semibold">
          Alarmas sin atender{" "}
          <span className="rounded bg-senal px-1.5 text-xs text-white">{alarms.length}</span>
        </h3>
        {alarms.length === 0 && (
          <p className="text-xs text-tinta-suave">No hay alarmas abiertas.</p>
        )}
        <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto">
          {alarms.map((e) => (
            <EventoLinea key={e.id} e={e} onAck={() => void ack(e.id)} />
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-2 rounded-md bg-white p-3 shadow-sm">
        <h3 className="font-semibold">Sensores instalados ({sensors.length})</h3>
        <ul className="flex flex-col divide-y divide-linea">
          {sensors.map((s) => (
            <li key={s.id} className="py-1.5">
              <button
                type="button"
                onClick={() => onSelectSensor(selectedSensorId === s.id ? null : s.id)}
                className={`flex w-full items-center gap-2 text-left text-xs ${
                  selectedSensorId === s.id ? "font-semibold" : ""
                }`}
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: s.open_alarms > 0 ? "#d21f2b" : "#0e7490" }}
                />
                <span className="font-mono">{s.code}</span>
                <span className="flex-1 truncate">{s.label}</span>
                <span className="tabular-nums text-tinta-suave">{s.battery_pct} %</span>
                {s.open_alarms > 0 && (
                  <span className="rounded bg-senal px-1 text-[10px] text-white">
                    {s.open_alarms}
                  </span>
                )}
              </button>
              {selected?.id === s.id && (
                <div className="mt-1.5 flex flex-col gap-1.5 pl-4 text-xs text-tinta-suave">
                  <span>
                    Cono de {s.range_m} m y ±{s.half_angle_deg}° · rumbo {s.heading_deg}° · última
                    señal {s.last_seen_at ? formatTime(s.last_seen_at) : "—"}
                    {s.last_event && ` · ${ZONE_EVENT_LABEL[s.last_event.kind].toLowerCase()}`}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => void simulate(s, false)}
                      className="rounded border border-rose-300 px-2 py-0.5 text-rose-800"
                    >
                      Simular intrusión
                    </button>
                    <button
                      type="button"
                      onClick={() => void simulate(s, true)}
                      className="rounded border border-emerald-300 px-2 py-0.5 text-emerald-800"
                    >
                      Simular rescatista con RFID
                    </button>
                    {s.incident_id && (
                      <button
                        type="button"
                        onClick={() => onOpenIncident(s.incident_id as string)}
                        className="rounded border border-linea px-2 py-0.5 text-tinta"
                      >
                        Ver incidente
                      </button>
                    )}
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-1 border-t border-linea pt-2">
          <label className="text-xs text-tinta-suave" htmlFor="zona-incidente">
            Instalar un sensor en un incidente estructural
          </label>
          <div className="flex gap-1.5">
            <select
              id="zona-incidente"
              className="min-w-0 flex-1 rounded border border-linea bg-white px-2 py-1 text-xs"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Elija un incidente…</option>
              {structural.map((i) => (
                <option key={i.id} value={i.id}>
                  {TRIAGE_LABEL[i.triage_level]} · {CATEGORY_LABEL[i.category]} ·{" "}
                  {i.barrio ?? "sin barrio"} · {i.report_count} rep.
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!target}
              onClick={() => void install()}
              className="rounded bg-sangre px-2 py-1 text-xs font-semibold text-white disabled:opacity-40"
            >
              Instalar
            </button>
          </div>
        </div>
        {msg && <p className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-900">{msg}</p>}
      </section>

      <section className="flex flex-col gap-2 rounded-md bg-white p-3 shadow-sm">
        <h3 className="font-semibold">Últimos eventos</h3>
        <ul className="flex flex-col gap-1">
          {recent.map((e) => (
            <EventoLinea key={e.id} e={e} />
          ))}
        </ul>
      </section>
    </div>
  );
}
