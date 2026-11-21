"""Decisión humana: PATCH /reports/{id} y PATCH /incidents/{id} (contracts/rest-api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.core.pipeline import Engine
from app.core.review import ReviewError, ReviewResult, review_incident, review_report
from app.db import get_session
from app.domain import ReportAction, Role
from app.models import Incident, Report
from app.routers.ingest import get_engine
from app.routers.mass_alerts import resolve_and_publish
from app.schemas import ReviewIn, ReviewOut
from app.serializers import events_out, incidents_out, reports_out

router = APIRouter(tags=["revisión humana"])


def _http(err: ReviewError) -> HTTPException:
    return HTTPException(err.status, detail={"detail": err.message, "code": err.code})


async def _respond(session: AsyncSession, result: ReviewResult, role: Role) -> ReviewOut:
    summaries = await incidents_out(session, result.touched_incidents or [result.incident])
    at = datetime.now(UTC).isoformat()
    for summary in summaries:
        bus.publish(
            "incident.status_changed",
            {
                "incident_id": str(summary.id),
                "status": summary.status.value,
                "actor_role": role.value,
                "at": at,
            },
        )
        bus.publish("incident.upserted", summary.model_dump(mode="json"))
    await resolve_and_publish(session, [s.mass_alert_id for s in summaries])
    main = next(s for s in summaries if s.id == result.incident.id)
    reports = await reports_out(session, result.reports[:1])
    return ReviewOut(
        report=reports[0] if reports else None, incident=main, events=events_out(result.events)
    )


@router.patch("/reports/{report_id}", response_model=ReviewOut)
async def patch_report(
    report_id: uuid.UUID,
    body: ReviewIn,
    role: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ReviewOut:
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(404, detail={"detail": "Reporte no existe", "code": "not_found"})
    try:
        result = await review_report(
            session,
            engine,
            report,
            ReportAction(body.action),
            role,
            body.note,
            body.duplicate_of_incident,
        )
    except ReviewError as err:
        raise _http(err) from err
    return await _respond(session, result, role)


@router.patch("/incidents/{incident_id}", response_model=ReviewOut)
async def patch_incident(
    incident_id: uuid.UUID,
    body: ReviewIn,
    role: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ReviewOut:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, detail={"detail": "Incidente no existe", "code": "not_found"})
    try:
        result = await review_incident(
            session,
            engine,
            incident,
            ReportAction(body.action),
            role,
            body.note,
            body.duplicate_of_incident,
        )
    except ReviewError as err:
        raise _http(err) from err
    return await _respond(session, result, role)
