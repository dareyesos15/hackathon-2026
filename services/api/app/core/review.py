"""Decisión humana sobre reportes e incidentes (data-model.md, máquinas de estado; FR-025).

La IA solo sugiere; decide un humano (principio III):
- Solo roles humanos ejecutan estas transiciones; el actor `sistema` nunca descarta.
- Descartar algo con riesgo vital exige una nota.
- Cada transición deja un `ReportEvent`; los reportes nunca se borran.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pipeline import Engine, refresh_trust
from app.domain import IncidentStatus, ReportAction, ReportStatus, Role
from app.models import Incident, Report, ReportEvent

TRANSITIONS: dict[ReportAction, tuple[frozenset[ReportStatus], ReportStatus]] = {
    ReportAction.confirmar: (frozenset({ReportStatus.en_revision}), ReportStatus.verificado),
    ReportAction.descartar: (frozenset({ReportStatus.en_revision}), ReportStatus.descartado),
    ReportAction.marcar_duplicado: (frozenset({ReportStatus.en_revision}), ReportStatus.duplicado),
    ReportAction.reabrir: (
        frozenset({ReportStatus.verificado, ReportStatus.descartado, ReportStatus.duplicado}),
        ReportStatus.en_revision,
    ),
}
INCIDENT_STATUS: dict[ReportAction, IncidentStatus] = {
    ReportAction.confirmar: IncidentStatus.verificado,
    ReportAction.descartar: IncidentStatus.descartado,
    ReportAction.reabrir: IncidentStatus.en_revision,
}


class ReviewError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class ReviewResult:
    incident: Incident
    reports: list[Report] = field(default_factory=list)
    events: list[ReportEvent] = field(default_factory=list)
    touched_incidents: list[Incident] = field(default_factory=list)


def _check(action: ReportAction, actor: Role, life_threat: bool, note: str | None) -> None:
    if actor == Role.sistema:
        raise ReviewError("forbidden", "El sistema no puede tomar decisiones de revisión", 403)
    if action == ReportAction.descartar and life_threat and not (note and note.strip()):
        raise ReviewError(
            "note_required_for_life_threat",
            "Para descartar un reporte con riesgo vital debe escribir una nota",
            422,
        )


def _event(
    report: Report,
    incident_id: uuid.UUID | None,
    actor: Role,
    action: ReportAction,
    note: str | None,
    extra: dict[str, str] | None = None,
) -> ReportEvent:
    payload: dict[str, str] = {"nota": note.strip()} if note and note.strip() else {}
    payload.update(extra or {})
    return ReportEvent(
        report_id=report.id,
        incident_id=incident_id,
        actor_role=actor,
        action=action,
        payload=payload,
        source="tablero PMU",
    )


async def _target(
    session: AsyncSession, target_id: uuid.UUID | None, current: uuid.UUID | None
) -> Incident | None:
    if target_id is None:
        return None
    if target_id == current:
        raise ReviewError("invalid_target", "El incidente destino es el mismo", 422)
    target = await session.get(Incident, target_id)
    if target is None:
        raise ReviewError("not_found", "El incidente destino no existe", 404)
    return target


async def review_report(
    session: AsyncSession,
    engine: Engine,
    report: Report,
    action: ReportAction,
    actor: Role,
    note: str | None = None,
    duplicate_of_incident: uuid.UUID | None = None,
) -> ReviewResult:
    allowed, new_status = TRANSITIONS[action]
    if report.status not in allowed:
        raise ReviewError(
            "invalid_transition",
            f"No se puede {action.value} un reporte en estado {report.status.value}",
            409,
        )
    _check(action, actor, report.is_life_threat, note)

    origin = await session.get(Incident, report.incident_id) if report.incident_id else None
    target = await _target(session, duplicate_of_incident, report.incident_id)
    extra = {"duplicado_de_incidente": str(target.id)} if target else {}
    report.status = new_status
    if target is not None:
        report.incident_id = target.id
    event = _event(report, report.incident_id, actor, action, note, extra)
    session.add(event)
    await session.flush()

    touched: list[Incident] = []
    for incident in (origin, target):
        if incident is None:
            continue
        await refresh_trust(session, engine, incident)
        if incident.report_count == 0:
            incident.status = IncidentStatus.descartado
        elif action == ReportAction.confirmar and incident is origin:
            incident.status = IncidentStatus.verificado
        elif incident.status == IncidentStatus.abierto:
            incident.status = IncidentStatus.en_revision
        touched.append(incident)
    await session.commit()
    main = target or origin
    assert main is not None
    return ReviewResult(main, [report], [event], touched)


async def review_incident(
    session: AsyncSession,
    engine: Engine,
    incident: Incident,
    action: ReportAction,
    actor: Role,
    note: str | None = None,
    duplicate_of_incident: uuid.UUID | None = None,
) -> ReviewResult:
    allowed, new_status = TRANSITIONS[action]
    _check(action, actor, incident.is_life_threat, note)
    if action == ReportAction.marcar_duplicado and duplicate_of_incident is None:
        raise ReviewError("target_required", "Indique el incidente del que este es duplicado", 422)
    target = await _target(session, duplicate_of_incident, incident.id)

    reports = list(
        (
            await session.execute(
                select(Report).where(
                    Report.incident_id == incident.id, Report.status.in_(list(allowed))
                )
            )
        ).scalars()
    )
    if not reports:
        raise ReviewError(
            "invalid_transition",
            f"No hay reportes a los que se pueda aplicar {action.value} en este incidente",
            409,
        )

    events: list[ReportEvent] = []
    extra = {"duplicado_de_incidente": str(target.id)} if target else {}
    for report in reports:
        report.status = new_status
        if target is not None:
            report.incident_id = target.id
        events.append(_event(report, incident.id, actor, action, note, extra))
    session.add_all(events)
    await session.flush()

    touched = [incident] + ([target] if target else [])
    for inc in touched:
        await refresh_trust(session, engine, inc)
    if target is not None:
        incident.status = IncidentStatus.descartado
        if target.status == IncidentStatus.abierto:
            target.status = IncidentStatus.en_revision
    else:
        incident.status = INCIDENT_STATUS.get(action, incident.status)
    await session.commit()
    return ReviewResult(target or incident, reports, events, touched)
