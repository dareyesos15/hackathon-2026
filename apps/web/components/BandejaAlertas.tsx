"use client";
/**
 * Bandeja de alertas (specs/002 US2): borradores pendientes y alertas emitidas. Solo el COE
 * ve "Aprobar", "Rechazar" y "Anular"; aprueba la versión que tiene en pantalla (FR-018).
 */
import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { formatInt, formatTime } from "@/lib/format";
import {
  ALERT_CHANNEL_LABEL,
  ALERT_STATUS_LABEL,
  ALERT_TYPE_LABEL,
  type AlertOut,
} from "@/lib/labels";

interface Props {
  isCoe: boolean;
  revision: number;
  onEdit: (alert: AlertOut) => void;
  onNew: () => void;
}

const STATUS_STYLE: Record<AlertOut["status"], string> = {
  borrador: "bg-amber-100 text-amber-900",
  emitida: "bg-red-600 text-white",
  rechazada: "bg-slate-200 text-slate-700",
  anulada: "bg-slate-200 text-tinta-suave line-through",
};

export function BandejaAlertas({ isCoe, revision, onEdit, onNew }: Props) {
  const [alerts, setAlerts] = useState<AlertOut[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    api.GET("/api/v1/alerts").then(({ data }) => {
      if (active && data) setAlerts(data.items);
    });
    return () => {
      active = false;
    };
  }, [revision, tick]);

  async function decide(alert: AlertOut, kind: "approve" | "reject" | "cancel") {
    setError(null);
    const reason = reasons[alert.id]?.trim() || null;
    const path = { params: { path: { alert_id: alert.id } } };
    const result =
      kind === "approve"
        ? await api.POST("/api/v1/alerts/{alert_id}/approve", {
            ...path,
            body: { version: alert.version },
          })
        : kind === "reject"
          ? await api.POST("/api/v1/alerts/{alert_id}/reject", {
              ...path,
              body: { version: alert.version, reason },
            })
          : await api.POST("/api/v1/alerts/{alert_id}/cancel", {
              ...path,
              body: { reason: reason ?? "" },
            });
    if (result.error) {
      const e = result.error as { detail?: string; code?: string };
      setError(
        e.code === "version_conflict"
          ? "El borrador cambió mientras lo revisaba: se recargó la versión nueva."
          : (e.detail ?? "No se pudo registrar la decisión"),
      );
    }
    setReasons((r) => ({ ...r, [alert.id]: "" }));
    setTick((t) => t + 1);
  }

  const drafts = alerts.filter((a) => a.status === "borrador");
  const others = alerts.filter((a) => a.status !== "borrador");

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">
          Alertas {isCoe ? "· bandeja del COE" : "· borradores para el COE"}
        </h2>
        <button
          type="button"
          onClick={onNew}
          className="rounded bg-amber-600 px-3 py-1 text-sm font-medium text-white"
        >
          Nueva alerta
        </button>
      </div>
      {error && <p className="text-xs text-rose-700">{error}</p>}

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold text-tinta-suave">
          Pendientes de aprobación ({formatInt(drafts.length)})
        </h3>
        {drafts.length === 0 && <p className="text-xs text-tinta-suave">No hay borradores.</p>}
        {drafts.map((a) => (
          <AlertCard key={a.id} alert={a}>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => onEdit(a)}
                className="rounded border border-slate-400 px-2 py-0.5 text-xs"
              >
                Editar
              </button>
              {isCoe && (
                <>
                  <button
                    type="button"
                    onClick={() => decide(a, "approve")}
                    className="rounded bg-red-700 px-2 py-0.5 text-xs font-medium text-white"
                  >
                    Aprobar y emitir (v{a.version})
                  </button>
                  <input
                    className="min-w-32 flex-1 rounded border border-linea px-1 text-xs"
                    placeholder="Motivo del rechazo"
                    value={reasons[a.id] ?? ""}
                    onChange={(e) => setReasons((r) => ({ ...r, [a.id]: e.target.value }))}
                  />
                  <button
                    type="button"
                    disabled={!reasons[a.id]?.trim()}
                    onClick={() => decide(a, "reject")}
                    className="rounded border border-slate-400 px-2 py-0.5 text-xs disabled:opacity-40"
                  >
                    Rechazar
                  </button>
                </>
              )}
            </div>
          </AlertCard>
        ))}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold text-tinta-suave">Historial</h3>
        {others.map((a) => (
          <AlertCard key={a.id} alert={a}>
            {isCoe && a.status === "emitida" && (
              <div className="mt-2 flex gap-2">
                <input
                  className="flex-1 rounded border border-linea px-1 text-xs"
                  placeholder="Motivo de la anulación"
                  value={reasons[a.id] ?? ""}
                  onChange={(e) => setReasons((r) => ({ ...r, [a.id]: e.target.value }))}
                />
                <button
                  type="button"
                  disabled={!reasons[a.id]?.trim()}
                  onClick={() => decide(a, "cancel")}
                  className="rounded border border-slate-400 px-2 py-0.5 text-xs disabled:opacity-40"
                >
                  Anular
                </button>
              </div>
            )}
          </AlertCard>
        ))}
      </section>
    </div>
  );
}

function AlertCard({ alert, children }: { alert: AlertOut; children?: React.ReactNode }) {
  const sms = alert.deliveries.find((d) => d.channel === "sms_cuadrillas");
  return (
    <article className="rounded-lg bg-white p-3 text-sm shadow-sm">
      <div className="flex justify-between gap-2">
        <span className="font-medium">{ALERT_TYPE_LABEL[alert.type]}</span>
        <span className={`rounded px-1.5 text-[10px] font-semibold ${STATUS_STYLE[alert.status]}`}>
          {ALERT_STATUS_LABEL[alert.status]}
        </span>
      </div>
      <p className="mt-1">{alert.message}</p>
      <p className="mt-1 text-[11px] text-tinta-suave">
        {alert.area_barrios.length > 0
          ? alert.area_barrios.join(", ")
          : alert.area_circle
            ? `Círculo de ${formatInt(alert.area_circle.radius_m)} m`
            : "Área"}{" "}
        · {alert.channels.map((c) => ALERT_CHANNEL_LABEL[c]).join(", ")} · creada por{" "}
        {alert.created_by_role} {formatTime(alert.created_at)}
        {alert.emitted_at && ` · emitida ${formatTime(alert.emitted_at)} por el COE`}
      </p>
      {sms && (
        <p className="text-[11px] text-tinta-suave">
          SMS a cuadrillas: {formatInt(sms.recipients_count ?? 0)} destinatarios
        </p>
      )}
      {alert.misinfo_signals.length > 0 && (
        <p className="text-[11px] text-rose-700">
          Señales de desinformación confirmadas: {alert.misinfo_signals.join(", ")}
        </p>
      )}
      {alert.close_reason && (
        <p className="text-[11px] text-tinta-suave">Motivo: {alert.close_reason}</p>
      )}
      {children}
    </article>
  );
}
