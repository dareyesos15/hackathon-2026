"""Consulta de incidentes: GET /incidents, GET /incidents/{id} (contracts/rest-api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.routing import build_routing
from app.auth import require_role
from app.config import get_settings
from app.core.dispatch import suggest
from app.db import get_session
from app.domain import (
    EMRE_FUNCTION_LABEL,
    Category,
    IncidentStatus,
    Role,
    TriageLevel,
    TrustLabel,
)
from app.models import Agency, Dispatch, Incident, Report, ReportEvent, Resource
from app.schemas import (
    AgencyRef,
    CandidateOut,
    DispatchSuggestion,
    IncidentDetail,
    IncidentList,
)
from app.serializers import (
    dispatches_out,
    events_out,
    incidents_out,
    reports_out,
    resources_out,
)

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


def _ref(agency: Agency | None) -> AgencyRef | None:
    return AgencyRef(id=agency.id, code=agency.code, name=agency.name) if agency else None


async def suggestion_out(session: AsyncSession, incident: Incident) -> DispatchSuggestion:
    """Función EMRE, agencia sugerida y candidatos por cercanía (FR-001, FR-003)."""
    found = await suggest(session, incident, build_routing(get_settings()))
    resources = await resources_out(
        session,
        [
            r
            for r in (
                await session.execute(
                    select(Resource).where(
                        Resource.id.in_([c.resource.id for c in found.candidates])
                    )
                )
            ).scalars()
        ],
    )
    by_id = {r.id: r for r in resources}
    return DispatchSuggestion(
        emre_function=found.emre_function,
        emre_function_label=EMRE_FUNCTION_LABEL[found.emre_function]
        if found.emre_function
        else None,
        suggested_agency=_ref(found.suggested_agency),
        alternative_agencies=[a for a in (_ref(x) for x in found.alternatives) if a],
        candidates=[
            CandidateOut(
                resource=by_id[c.resource.id],
                agency_code=c.resource.agency_code,
                distance_m=round(c.distance_m),
                eta_min=round(c.eta_min, 1),
            )
            for c in found.candidates
            if c.resource.id in by_id
        ],
        fallback_used=found.fallback_used,
    )


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
    dispatches = list(
        (
            await session.execute(
                select(Dispatch)
                .where(Dispatch.incident_id == incident.id)
                .order_by(Dispatch.created_at)
            )
        ).scalars()
    )
    return IncidentDetail(
        **summary.model_dump(),
        trust_breakdown=incident.trust_breakdown,
        reports=await reports_out(session, reports),
        events=events_out(events),
        dispatches=await dispatches_out(session, dispatches),
        suggestion=await suggestion_out(session, incident),
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
