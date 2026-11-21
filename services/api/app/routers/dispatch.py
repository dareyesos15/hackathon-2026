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
    record_track,
    update_dispatch,
)
from app.db import get_session
from app.domain import DispatchStatus, ResourceStatus, Role, TrackOrigin
from app.models import Agency, Dispatch, Incident, Resource, ResourceTrack
from app.schemas import (
    AgencyList,
    AgencyOut,
    DispatchIn,
    DispatchList,
    DispatchOut,
    DispatchPatchIn,
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
    role: Role = Depends(require_role(Role.agencia, Role.operador_pmu)),
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
