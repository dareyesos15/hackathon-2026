"""Alerta masiva de toda la ciudad: sesión propia, resolución y reporte final.

- Mientras una alerta masiva está activa, todo incidente nuevo pertenece a su sesión
  (`incidents.mass_alert_id`) y solo se agrupa con incidentes de la misma sesión.
- Se resuelve sola cuando todos sus incidentes están cerrados (atendidos o descartados) y no
  quedan despachos activos. Entonces se guarda el reporte final: problemas, trazabilidad
  (bitácora y despachos) y tiempos de solución.
- El reloj de cada incidente arranca cuando el sistema lo registra (`created_at`), no en la hora
  declarada del hecho: así los tiempos miden la operación del PMU, también en la reproducción.
- Sin datos personales (Ley 1581): solo categorías, barrios, roles, agencias y notas redactadas.
"""

from __future__ import annotations

import statistics
import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.privacy import redact
from app.domain import (
    ACTIVE_DISPATCH,
    DispatchStatus,
    IncidentStatus,
    MassAlertStatus,
    ReportAction,
    TriageLevel,
)
from app.models import Agency, Dispatch, Incident, MassAlert, Report, ReportEvent, Resource

CLOSED = frozenset({IncidentStatus.atendido, IncidentStatus.descartado})
CLOSING_ACTIONS = frozenset({ReportAction.cerrar_atendido, ReportAction.descartar})
TRIAGE_ORDER = [TriageLevel.critico, TriageLevel.alto, TriageLevel.medio, TriageLevel.bajo]
REPORT_VERSION = 1


class MassAlertError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


async def active_mass_alert(session: AsyncSession) -> MassAlert | None:
    return await session.scalar(
        select(MassAlert).where(MassAlert.status == MassAlertStatus.activa).limit(1)
    )


async def progress(session: AsyncSession, mass_alert_id: uuid.UUID) -> tuple[int, int]:
    """(incidentes de la sesión, incidentes cerrados)."""
    total, closed = (
        await session.execute(
            select(
                func.count(Incident.id),
                func.count(Incident.id).filter(Incident.status.in_(list(CLOSED))),
            ).where(Incident.mass_alert_id == mass_alert_id, Incident.report_count > 0)
        )
    ).one()
    return int(total), int(closed)


async def _active_dispatches(session: AsyncSession, mass_alert_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count(Dispatch.id))
            .join(Incident, Incident.id == Dispatch.incident_id)
            .where(
                Incident.mass_alert_id == mass_alert_id,
                Dispatch.status.in_(list(ACTIVE_DISPATCH)),
            )
        )
        or 0
    )


def _minutes(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return round(max((b - a).total_seconds(), 0.0) / 60.0, 1)


def _stats(values: Sequence[float | None]) -> dict[str, float | int | None]:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "promedio": None, "mediana": None, "maximo": None}
    return {
        "n": len(vals),
        "promedio": round(statistics.fmean(vals), 1),
        "mediana": round(statistics.median(vals), 1),
        "maximo": round(max(vals), 1),
    }


def _note(payload: dict[str, Any]) -> str | None:
    note = payload.get("nota")
    return redact(str(note)).text if note else None


async def build_report(
    session: AsyncSession, alert: MassAlert, now: datetime | None = None
) -> dict[str, Any]:
    """Reporte de la alerta masiva. Si sigue activa, es preliminar (corte = ahora)."""
    now = now or datetime.now(UTC)
    incidents = list(
        (
            await session.execute(
                select(Incident)
                .where(Incident.mass_alert_id == alert.id, Incident.report_count > 0)
                .order_by(Incident.created_at)
            )
        ).scalars()
    )
    ids = [i.id for i in incidents]

    events: dict[uuid.UUID, list[ReportEvent]] = {i: [] for i in ids}
    channels: Counter[str] = Counter()
    report_counts: Counter[uuid.UUID] = Counter()
    dispatch_rows: list[tuple[Dispatch, str, str, str]] = []
    if ids:
        for ev in (
            await session.execute(
                select(ReportEvent).where(ReportEvent.incident_id.in_(ids)).order_by(ReportEvent.at)
            )
        ).scalars():
            assert ev.incident_id is not None
            events[ev.incident_id].append(ev)
        for incident_id, channel, n in (
            await session.execute(
                select(Report.incident_id, Report.channel, func.count(Report.id))
                .where(Report.incident_id.in_(ids))
                .group_by(Report.incident_id, Report.channel)
            )
        ).all():
            channels[channel.value] += int(n)
            if incident_id is not None:
                report_counts[incident_id] += int(n)
        dispatch_rows = [
            (d, code, name, label)
            for d, code, name, label in (
                await session.execute(
                    select(Dispatch, Agency.code, Agency.name, Resource.label)
                    .join(Agency, Agency.id == Dispatch.agency_id)
                    .join(Resource, Resource.id == Dispatch.resource_id)
                    .where(Dispatch.incident_id.in_(ids))
                    .order_by(Dispatch.created_at)
                )
            ).all()
        ]
    dispatches: dict[uuid.UUID, list[tuple[Dispatch, str, str, str]]] = {i: [] for i in ids}
    for row in dispatch_rows:
        dispatches[row[0].incident_id].append(row)

    problems: list[dict[str, Any]] = []
    by_triage: dict[str, list[float | None]] = {t.value: [] for t in TRIAGE_ORDER}
    to_dispatch: list[float | None] = []
    to_arrival: list[float | None] = []
    to_verify: list[float | None] = []
    for inc in incidents:
        evs = events[inc.id]
        start = inc.created_at
        verified_at = next((e.at for e in evs if e.action == ReportAction.confirmar), None)
        closing = [e for e in evs if e.action in CLOSING_ACTIONS]
        closed_at = closing[-1].at if (closing and inc.status in CLOSED) else None
        if closed_at is None and inc.status in CLOSED:
            closed_at = inc.updated_at
        valid = [d for d, *_ in dispatches[inc.id] if d.status != DispatchStatus.cancelado]
        first_dispatch = min((d.created_at for d in valid), default=None)
        first_arrival = min((d.arrived_at for d in valid if d.arrived_at), default=None)

        # Bitácora: un evento por decisión (las acciones sobre el incidente se aplican a cada
        # reporte; se agrupan por acción, rol y segundo).
        trace: list[dict[str, Any]] = []
        seen: dict[tuple[str, str, str], dict[str, Any]] = {}
        for e in evs:
            key = (e.action.value, e.actor_role.value, e.at.replace(microsecond=0).isoformat())
            if key in seen:
                seen[key]["reportes"] += 1
                continue
            item = {
                "at": e.at.isoformat(),
                "accion": e.action.value,
                "rol": e.actor_role.value,
                "reportes": 1,
                "nota": _note(e.payload),
            }
            seen[key] = item
            trace.append(item)

        resolution = _minutes(start, closed_at)
        by_triage[inc.triage_level.value].append(resolution)
        to_dispatch.append(_minutes(start, first_dispatch))
        to_arrival.append(_minutes(start, first_arrival))
        to_verify.append(_minutes(start, verified_at))
        problems.append(
            {
                "incident_id": str(inc.id),
                "categoria": inc.category.value,
                "triaje": inc.triage_level.value,
                "riesgo_vital": inc.is_life_threat,
                "barrio": inc.barrio,
                "manzana_id": inc.manzana_id,
                "estado_final": inc.status.value,
                "reportes": report_counts.get(inc.id, inc.report_count),
                "fuentes_independientes": inc.independent_sources,
                "personas_afectadas": inc.people_affected,
                "trust_score": inc.trust_score,
                "registrado_at": start.isoformat(),
                "verificado_at": verified_at.isoformat() if verified_at else None,
                "primer_despacho_at": first_dispatch.isoformat() if first_dispatch else None,
                "primera_llegada_at": first_arrival.isoformat() if first_arrival else None,
                "cerrado_at": closed_at.isoformat() if closed_at else None,
                "min_a_verificacion": _minutes(start, verified_at),
                "min_a_despacho": _minutes(start, first_dispatch),
                "min_a_llegada": _minutes(start, first_arrival),
                "min_a_solucion": resolution,
                "despachos": [
                    {
                        "agencia": code,
                        "agencia_nombre": name,
                        "recurso": label,
                        "estado": d.status.value,
                        "refuerzo": d.is_reinforcement,
                        "creado_at": d.created_at.isoformat(),
                        "llegada_at": d.arrived_at.isoformat() if d.arrived_at else None,
                        "cierre_at": d.closed_at.isoformat() if d.closed_at else None,
                        "distancia_m": d.distance_m,
                    }
                    for d, code, name, label in dispatches[inc.id]
                ],
                "bitacora": trace,
            }
        )

    all_resolution = [p["min_a_solucion"] for p in problems]
    agencies = Counter(
        code for d, code, _, _ in dispatch_rows if d.status != DispatchStatus.cancelado
    )
    end = alert.resolved_at or now
    return {
        "version": REPORT_VERSION,
        "preliminar": alert.status == MassAlertStatus.activa,
        "generado_at": now.isoformat(),
        "corte_at": end.isoformat(),
        "fuente": "Dacora · SST (datos SIMULADOS)",
        "alerta": {
            "id": str(alert.id),
            "titulo": alert.title,
            "evento": alert.event_type.value,
            "descripcion": alert.description,
            "inicio_at": alert.started_at.isoformat(),
            "fin_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "duracion_min": _minutes(alert.started_at, end),
            "creada_por": alert.created_by_role.value,
        },
        "resumen": {
            "incidentes": len(incidents),
            "reportes": sum(report_counts.values()),
            "atendidos": sum(1 for i in incidents if i.status == IncidentStatus.atendido),
            "descartados": sum(1 for i in incidents if i.status == IncidentStatus.descartado),
            "abiertos": sum(1 for i in incidents if i.status not in CLOSED),
            "riesgo_vital": sum(1 for i in incidents if i.is_life_threat),
            "despachos": sum(1 for d, *_ in dispatch_rows if d.status != DispatchStatus.cancelado),
            "por_triaje": dict(Counter(i.triage_level.value for i in incidents)),
            "por_categoria": dict(Counter(i.category.value for i in incidents).most_common()),
            "por_barrio": dict(Counter(i.barrio or "sin ubicar" for i in incidents).most_common()),
            "por_canal": dict(channels.most_common()),
            "por_agencia": dict(agencies.most_common()),
        },
        "tiempos": {
            "solucion": _stats(all_resolution),
            "verificacion": _stats(to_verify),
            "despacho": _stats(to_dispatch),
            "llegada": _stats(to_arrival),
            "solucion_por_triaje": {t: _stats(v) for t, v in by_triage.items() if v},
        },
        "problemas": problems,
    }


async def check_resolution(
    session: AsyncSession, mass_alert_ids: Sequence[uuid.UUID | None]
) -> list[MassAlert]:
    """Resuelve las alertas masivas activas cuyos incidentes ya están todos cerrados.

    Devuelve las alertas resueltas en esta llamada (para publicar el evento).
    """
    resolved: list[MassAlert] = []
    for mid in {m for m in mass_alert_ids if m is not None}:
        alert = await session.get(MassAlert, mid, with_for_update=True)
        if alert is None or alert.status != MassAlertStatus.activa:
            continue
        total, closed = await progress(session, mid)
        if total == 0 or closed < total or await _active_dispatches(session, mid) > 0:
            continue
        now = datetime.now(UTC)
        alert.status = MassAlertStatus.resuelta
        alert.resolved_at = now
        alert.version += 1
        alert.final_report = await build_report(session, alert, now)
        resolved.append(alert)
    # Commit también sin cambios: libera el bloqueo sin expirar los objetos del llamador.
    await session.commit()
    return resolved
