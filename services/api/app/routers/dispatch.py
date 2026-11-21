"""Despacho y trazabilidad de recursos (specs/002 US1; contracts/rest-api.md §Despachos)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.adapters.routing import RoutingProvider, build_routing
from app.auth import require_role
from app.config import get_settings
from app.core.dispatch import (
    DispatchError,
    TrackResult,
    create_dispatches,
    execute_plan,
    record_track,
    routing_of,
    update_dispatch,
)
from app.core.recipients import Recipient
from app.db import get_session
from app.domain import (
    ACTIVE_DISPATCH,
    DispatchStatus,
    IncidentStatus,
    ResourceStatus,
    Role,
    TrackOrigin,
)
from app.models import Agency, Dispatch, Incident, Report, Resource, ResourceTrack
from app.schemas import (
    AgencyList,
    AgencyOut,
    AgencyRef,
    DispatchIn,
    DispatchList,
    DispatchOut,
    DispatchPatchIn,
    DispatchPlanIn,
    InboxItem,
    InboxList,
    ResourceList,
    TrackIn,
    TrackList,
    TrackOut,
)
from app.serializers import dispatches_out, incidents_out, resources_out, tracks_out

router = APIRouter(tags=["despacho"])

READERS = (Role.operador_pmu, Role.coe, Role.agencia)


def get_routing() -> RoutingProvider:
    return build_routing(get_settings())


async def _http(session: AsyncSession, err: DispatchError) -> HTTPException:
    body: dict[str, object] = {"detail": err.message, "code": err.code}
    for key, value in err.extra.items():
        if key == "active":
            active = await dispatches_out(session, value)
            body[key] = [d.model_dump(mode="json") for d in active]
        else:
            body[key] = value
    return HTTPException(err.status, detail=body)


async def publish_dispatches(session: AsyncSession, dispatches: Sequence[Dispatch]) -> None:
    """Eventos en vivo tras un cambio de despacho (contracts/sse-events.md)."""
    out = await dispatches_out(session, dispatches)
    for item in out:
        bus.publish("dispatch.upserted", item.model_dump(mode="json"))
    incidents = [
        i
        for i in (
            await session.execute(
                select(Incident).where(Incident.id.in_({d.incident_id for d in dispatches}))
            )
        ).scalars()
    ]
    for summary in await incidents_out(session, incidents):
        bus.publish("incident.upserted", summary.model_dump(mode="json"))


async def publish_track(session: AsyncSession, result: TrackResult) -> None:
    track = (await tracks_out(session, [result.track]))[0]
    if result.moved:
        bus.publish(
            "resource.moved",
            {
                "resource_id": str(result.resource.id),
                "code": result.resource.code,
                "status": result.resource.status.value,
                "lat": track.lat,
                "lon": track.lon,
                "kind": track.kind.value,
                "at": track.at.isoformat(),
                "dispatch_id": str(track.dispatch_id) if track.dispatch_id else None,
            },
        )
    if result.dispatch is not None:
        await publish_dispatches(session, [result.dispatch])


# --------------------------------------------------------------------- agencias y recursos


@router.get("/agencies", response_model=AgencyList)
async def list_agencies(
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> AgencyList:
    counts = (
        await session.execute(
            select(
                Resource.agency_id,
                func.count(),
                func.count().filter(Resource.status == ResourceStatus.disponible),
            ).group_by(Resource.agency_id)
        )
    ).all()
    by_agency = {aid: (total, available) for aid, total, available in counts}
    agencies = (await session.execute(select(Agency).order_by(Agency.name))).scalars()
    return AgencyList(
        items=[
            AgencyOut(
                id=a.id,
                code=a.code,
                name=a.name,
                emre_function=a.emre_function,
                resources_total=by_agency.get(a.id, (0, 0))[0],
                resources_available=by_agency.get(a.id, (0, 0))[1],
            )
            for a in agencies
        ]
    )


@router.get("/resources", response_model=ResourceList)
async def list_resources(
    agency_id: uuid.UUID | None = None,
    status_: ResourceStatus | None = Query(default=None, alias="status"),
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> ResourceList:
    stmt = select(Resource).order_by(Resource.code)
    if agency_id:
        stmt = stmt.where(Resource.agency_id == agency_id)
    if status_:
        stmt = stmt.where(Resource.status == status_)
    resources = list((await session.execute(stmt)).scalars())
    return ResourceList(items=await resources_out(session, resources), cutoff_at=datetime.now(UTC))


async def _resource(session: AsyncSession, resource_id: uuid.UUID) -> Resource:
    resource = await session.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(404, detail={"detail": "Recurso no existe", "code": "not_found"})
    return resource


@router.get("/resources/{resource_id}/tracks", response_model=TrackList)
async def list_tracks(
    resource_id: uuid.UUID,
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> TrackList:
    await _resource(session, resource_id)
    tracks = list(
        (
            await session.execute(
                select(ResourceTrack)
                .where(ResourceTrack.resource_id == resource_id)
                .order_by(ResourceTrack.at, ResourceTrack.created_at)
            )
        ).scalars()
    )
    return TrackList(items=await tracks_out(session, tracks))


@router.post(
    "/resources/{resource_id}/tracks", response_model=TrackOut, status_code=status.HTTP_201_CREATED
)
async def post_track(
    resource_id: uuid.UUID,
    body: TrackIn,
    role: Role = Depends(require_role(Role.agencia, Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> TrackOut:
    """Punto de paso manual o de un lector real (FR-008). `llegada` → despacho `en_sitio`."""
    resource = await _resource(session, resource_id)
    try:
        result = await record_track(
            session,
            resource,
            kind=body.kind,
            origin=TrackOrigin.manual,
            lat=body.lat,
            lon=body.lon,
            at=body.at or datetime.now(UTC),
            actor=role,
        )
    except DispatchError as err:
        error = await _http(session, err)
        await session.rollback()
        raise error from err
    await publish_track(session, result)
    return (await tracks_out(session, [result.track]))[0]


# ---------------------------------------------------------------------------- despachos


@router.post(
    "/dispatches",
    response_model=DispatchList,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Confirmación repetida: despacho existente"}},
)
async def post_dispatch(
    body: DispatchIn,
    response: Response,
    role: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
    routing: RoutingProvider = Depends(get_routing),
) -> DispatchList:
    try:
        result = await create_dispatches(
            session,
            client_uuid=body.client_uuid,
            incident_id=body.incident_id,
            resource_ids=body.resource_ids,
            is_reinforcement=body.is_reinforcement,
            justification=body.justification,
            actor=role,
            routing=routing,
            now=datetime.now(UTC),
        )
    except DispatchError as err:
        error = await _http(session, err)
        await session.rollback()
        raise error from err
    if result.created:
        await publish_dispatches(session, result.dispatches)
    else:
        response.status_code = status.HTTP_200_OK
    return DispatchList(
        items=await dispatches_out(session, result.dispatches), cutoff_at=datetime.now(UTC)
    )


@router.get("/dispatches", response_model=DispatchList)
async def list_dispatches(
    incident_id: uuid.UUID | None = None,
    agency_id: uuid.UUID | None = None,
    status_: DispatchStatus | None = Query(default=None, alias="status"),
    since: datetime | None = Query(default=None, description="Cambiados después de"),
    role: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> DispatchList:
    if role == Role.agencia and agency_id is None:
        raise HTTPException(
            422, detail={"detail": "Indique su agencia (agency_id)", "code": "agency_required"}
        )
    stmt = select(Dispatch).order_by(Dispatch.created_at.desc()).limit(500)
    if incident_id:
        stmt = stmt.where(Dispatch.incident_id == incident_id)
    if agency_id:
        stmt = stmt.where(Dispatch.agency_id == agency_id)
    if status_:
        stmt = stmt.where(Dispatch.status == status_)
    if since:
        changed = func.greatest(Dispatch.created_at, Dispatch.arrived_at, Dispatch.closed_at)
        stmt = stmt.where(changed > since)
    dispatches = list((await session.execute(stmt)).scalars())
    items = await dispatches_out(session, dispatches)
    return DispatchList(items=items, cutoff_at=datetime.now(UTC))


@router.patch("/dispatches/{dispatch_id}", response_model=DispatchOut)
async def patch_dispatch(
    dispatch_id: uuid.UUID,
    body: DispatchPatchIn,
    role: Role = Depends(require_role(Role.agencia, Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> DispatchOut:
    dispatch = (
        await session.execute(select(Dispatch).where(Dispatch.id == dispatch_id).with_for_update())
    ).scalar_one_or_none()
    if dispatch is None:
        raise HTTPException(404, detail={"detail": "Despacho no existe", "code": "not_found"})
    try:
        await update_dispatch(
            session, dispatch, action=body.action, actor=role, note=body.note, now=datetime.now(UTC)
        )
    except DispatchError as err:
        error = await _http(session, err)
        await session.rollback()
        raise error from err
    await session.refresh(dispatch)
    await publish_dispatches(session, [dispatch])
    return (await dispatches_out(session, [dispatch]))[0]


# ------------------------------------------------------- avisos a agencias y plan multiagencia

OPEN_INCIDENT = (IncidentStatus.abierto, IncidentStatus.en_revision, IncidentStatus.verificado)
ROLE_ORDER = {"lider": 0, "apoyo": 1, "informada": 2}
TRIAGE_ORDER = {"critico": 0, "alto": 1, "medio": 2, "bajo": 3}


@router.get("/agencies/{agency_id}/inbox", response_model=InboxList)
async def agency_inbox(
    agency_id: uuid.UUID,
    include_held: bool = Query(default=False, description="Incluir avisos retenidos"),
    limit: int = Query(default=100, ge=1, le=500),
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> InboxList:
    """Incidentes abiertos que le llegan a la agencia según las reglas EMRE, con su papel.

    Los avisos de posibles falsos sin riesgo vital quedan retenidos hasta que el PMU los
    verifique; los de riesgo vital llegan siempre (CLAUDE.md §0.6).
    """
    agency = await session.get(Agency, agency_id)
    if agency is None:
        raise HTTPException(404, detail={"detail": "Agencia no existe", "code": "not_found"})
    incidents = list(
        (
            await session.execute(
                select(Incident)
                .where(Incident.report_count > 0, Incident.status.in_(OPEN_INCIDENT))
                .order_by(Incident.last_seen.desc())
                .limit(2000)
            )
        ).scalars()
    )
    texts: dict[uuid.UUID, list[str]] = {}
    for incident_id, text in await session.execute(
        select(Report.incident_id, Report.text_redacted).where(
            Report.incident_id.in_([i.id for i in incidents])
        )
    ):
        if incident_id is not None:
            texts.setdefault(incident_id, []).append(text)
    dispatched = {
        iid
        for (iid,) in await session.execute(
            select(Dispatch.incident_id).where(
                Dispatch.agency_id == agency.id, Dispatch.status.in_(list(ACTIVE_DISPATCH))
            )
        )
    }
    picked: list[tuple[Incident, Recipient, bool, bool]] = []
    for incident in incidents:
        routing = routing_of(incident, texts.get(incident.id, []))
        recipient = routing.for_agency(agency.code)
        if recipient is None or (routing.held and not include_held):
            continue
        picked.append((incident, recipient, incident.id in dispatched, routing.notify_coe))
    picked.sort(
        key=lambda p: (
            p[2],
            TRIAGE_ORDER[p[0].triage_level.value],
            ROLE_ORDER[p[1].role.value],
            -p[0].last_seen.timestamp(),
        )
    )
    picked = picked[:limit]
    summaries = await incidents_out(session, [p[0] for p in picked])
    items = [
        InboxItem(
            incident=summary,
            role=recipient.role,
            emre_task=recipient.task,
            reason=recipient.reason,
            dispatched=is_dispatched,
            notify_coe=notify_coe,
        )
        for summary, (_, recipient, is_dispatched, notify_coe) in zip(
            summaries, picked, strict=True
        )
    ]
    return InboxList(
        agency=AgencyRef(id=agency.id, code=agency.code, name=agency.name),
        items=items,
        cutoff_at=datetime.now(UTC),
    )


@router.post(
    "/incidents/{incident_id}/dispatch-plan",
    response_model=DispatchList,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Confirmación repetida: despachos existentes"}},
)
async def post_dispatch_plan(
    incident_id: uuid.UUID,
    body: DispatchPlanIn,
    response: Response,
    role: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
    routing: RoutingProvider = Depends(get_routing),
) -> DispatchList:
    """Genera el despacho multiagencia propuesto: un recurso por agencia líder y de apoyo.

    Es la confirmación humana del plan (la IA solo sugiere). Idempotente por `client_uuid`.
    """
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, detail={"detail": "Incidente no existe", "code": "not_found"})
    try:
        result = await execute_plan(
            session,
            client_uuid=body.client_uuid,
            incident=incident,
            resource_ids=body.resource_ids,
            actor=role,
            routing=routing,
            now=datetime.now(UTC),
        )
    except DispatchError as err:
        error = await _http(session, err)
        await session.rollback()
        raise error from err
    if result.created:
        await publish_dispatches(session, result.dispatches)
    else:
        response.status_code = status.HTTP_200_OK
    return DispatchList(
        items=await dispatches_out(session, result.dispatches), cutoff_at=datetime.now(UTC)
    )
