"""Consulta de incidentes: GET /incidents, GET /incidents/{id} (contracts/rest-api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.db import get_session
from app.domain import Category, IncidentStatus, Role, TriageLevel, TrustLabel
from app.models import Incident, Report, ReportEvent
from app.schemas import IncidentDetail, IncidentList
from app.serializers import events_out, incidents_out, reports_out

router = APIRouter(prefix="/incidents", tags=["incidentes"])

TRIAGE_ORDER = case(
    {
        TriageLevel.critico.value: 4,
        TriageLevel.alto.value: 3,
        TriageLevel.medio.value: 2,
        TriageLevel.bajo.value: 1,
    },
    value=Incident.triage_level,
)


@router.get("", response_model=IncidentList)
async def list_incidents(
    triage: TriageLevel | None = None,
    status_: IncidentStatus | None = Query(default=None, alias="status"),
    category: Category | None = None,
    trust_label: TrustLabel | None = None,
    since: datetime | None = Query(default=None, description="Actualizados después de"),
    limit: int = Query(default=500, ge=1, le=2000),
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> IncidentList:
    cutoff = datetime.now(UTC)
    stmt = select(Incident).where(Incident.report_count > 0)
    if triage:
        stmt = stmt.where(Incident.triage_level == triage)
    if status_:
        stmt = stmt.where(Incident.status == status_)
    if category:
        stmt = stmt.where(Incident.category == category)
    if trust_label:
        stmt = stmt.where(Incident.trust_label == trust_label)
    if since:
        stmt = stmt.where(Incident.updated_at > since)
    stmt = stmt.order_by(TRIAGE_ORDER.desc(), Incident.first_seen).limit(limit)
    rows = list((await session.execute(stmt)).scalars())
    return IncidentList(items=await incidents_out(session, rows), cutoff_at=cutoff)


async def incident_detail(session: AsyncSession, incident: Incident) -> IncidentDetail:
    summary = (await incidents_out(session, [incident]))[0]
    reports = list(
        (
            await session.execute(
                select(Report).where(Report.incident_id == incident.id).order_by(Report.occurred_at)
            )
        ).scalars()
    )
    events = list(
        (
            await session.execute(
                select(ReportEvent)
                .where(ReportEvent.incident_id == incident.id)
                .order_by(ReportEvent.at, ReportEvent.created_at)
            )
        ).scalars()
    )
    return IncidentDetail(
        **summary.model_dump(),
        trust_breakdown=incident.trust_breakdown,
        reports=await reports_out(session, reports),
        events=events_out(events),
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> IncidentDetail:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"detail": "Incidente no existe", "code": "not_found"}
        )
    return await incident_detail(session, incident)
