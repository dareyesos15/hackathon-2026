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
from app.core.dispatch import (
    active_agency_codes,
    dispatch_plan,
    incident_routing,
    suggest,
)
from app.core.recipients import Routing
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
    IncidentRouting,
    IncidentSummary,
    PlanLineOut,
    RecipientOut,
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
    role: Role = Depends(require_role(Role.operador_pmu, Role.coe, Role.publico)),
    session: AsyncSession = Depends(get_session),
) -> IncidentList:
    """Incidentes con triaje. El público (sin sesión) ve la misma matriz, sin los descartados y
    con la ubicación redondeada a ~100 m (sin direcciones exactas; Ley 1581). Los incidentes no
    llevan texto de reportes ni datos personales."""
    cutoff = datetime.now(UTC)
    stmt = select(Incident).where(Incident.report_count > 0)
    if role == Role.publico:
        stmt = stmt.where(Incident.status != IncidentStatus.descartado)
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
    items = await incidents_out(session, rows)
    if role == Role.publico:
        items = [_public_incident(i) for i in items]
    return IncidentList(items=items, cutoff_at=cutoff)


PUBLIC_COORD_DECIMALS = 3  # ~110 m: ubica la manzana, no la puerta


def _public_incident(item: IncidentSummary) -> IncidentSummary:
    def r(v: float | None) -> float | None:
        return round(v, PUBLIC_COORD_DECIMALS) if v is not None else None

    return item.model_copy(update={"lat": r(item.lat), "lon": r(item.lon)})


def _ref(agency: Agency | None) -> AgencyRef | None:
    return AgencyRef(id=agency.id, code=agency.code, name=agency.name) if agency else None


async def suggestion_out(
    session: AsyncSession, incident: Incident, recipients: Routing | None = None
) -> DispatchSuggestion:
    """Función EMRE, agencia sugerida y candidatos por cercanía (FR-001, FR-003)."""
    found = await suggest(session, incident, build_routing(get_settings()), recipients)
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


async def routing_out(
    session: AsyncSession, incident: Incident, recipients: Routing
) -> IncidentRouting:
    """Destinatarios del incidente y plan multiagencia con el recurso más cercano por agencia."""
    agencies = {a.code: a for a in (await session.execute(select(Agency))).scalars()}
    dispatched = await active_agency_codes(session, incident.id)
    lines = await dispatch_plan(session, incident, build_routing(get_settings()), recipients)
    unit_ids = [line.unit.resource_id for line in lines if line.unit is not None]
    by_id = {
        r.id: r
        for r in await resources_out(
            session,
            list(
                (await session.execute(select(Resource).where(Resource.id.in_(unit_ids)))).scalars()
            ),
        )
    }
    plan: list[PlanLineOut] = []
    for line in lines:
        agency = _ref(agencies.get(line.recipient.agency))
        if agency is None:
            continue
        candidate = None
        if line.unit is not None and line.unit.resource_id in by_id:
            candidate = CandidateOut(
                resource=by_id[line.unit.resource_id],
                agency_code=line.unit.agency,
                distance_m=round(line.unit.distance_m),
                eta_min=round(line.unit.eta_min, 1),
            )
        plan.append(
            PlanLineOut(
                agency=agency,
                role=line.recipient.role,
                emre_task=line.recipient.task,
                candidate=candidate,
                already_dispatched=line.already_dispatched,
            )
        )
    recipients_out = [
        RecipientOut(
            agency=ref,
            role=r.role,
            emre_function=r.emre_function,
            emre_function_label=EMRE_FUNCTION_LABEL[r.emre_function],
            emre_task=r.task,
            reason=r.reason,
            dispatched=r.agency in dispatched,
        )
        for r in recipients.recipients
        if (ref := _ref(agencies.get(r.agency))) is not None
    ]
    return IncidentRouting(
        recipients=recipients_out,
        notify_coe=recipients.notify_coe,
        coe_reason=recipients.coe_reason,
        held=recipients.held,
        hold_reason=recipients.hold_reason,
        notes=list(recipients.notes),
        plan=plan,
        plan_resource_ids=[p.candidate.resource.id for p in plan if p.candidate],
    )


async def incident_detail(session: AsyncSession, incident: Incident) -> IncidentDetail:
    summary = (await incidents_out(session, [incident]))[0]
    recipients = await incident_routing(session, incident)
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
        suggestion=await suggestion_out(session, incident, recipients),
        routing=await routing_out(session, incident, recipients),
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
