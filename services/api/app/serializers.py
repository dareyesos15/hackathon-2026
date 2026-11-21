"""Conversión de modelos ORM a esquemas de salida (incluye lat/lon desde PostGIS)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import ACTIVE_DISPATCH, DispatchStatus, IncidentStatus
from app.models import Agency, Dispatch, Incident, Report, ReportEvent, Resource, ResourceTrack
from app.schemas import (
    AgencyRef,
    DispatchOut,
    IncidentSummary,
    ReportEventOut,
    ReportOut,
    ResourceOut,
    TrackOut,
)

OPEN_FOR_DISPATCH = (IncidentStatus.abierto, IncidentStatus.en_revision, IncidentStatus.verificado)


async def _coords(
    session: AsyncSession, model: type[Report] | type[Incident], ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[float | None, float | None]]:
    if not ids:
        return {}
    column = Report.geom if model is Report else Incident.centroid
    rows = (
        await session.execute(
            select(model.id, func.ST_Y(column), func.ST_X(column)).where(model.id.in_(ids))
        )
    ).all()
    return {rid: (lat, lon) for rid, lat, lon in rows}


async def reports_out(session: AsyncSession, reports: Sequence[Report]) -> list[ReportOut]:
    coords = await _coords(session, Report, [r.id for r in reports])
    out = []
    for r in reports:
        lat, lon = coords.get(r.id, (None, None))
        out.append(
            ReportOut(
                id=r.id,
                client_uuid=r.client_uuid,
                channel=r.channel,
                received_at=r.received_at,
                occurred_at=r.occurred_at,
                text_redacted=r.text_redacted,
                location_text=r.location_text,
                lat=lat,
                lon=lon,
                geo_precision=r.geo_precision,
                manzana_id=r.manzana_id,
                barrio=r.barrio,
                category=r.category,
                severity=r.severity,
                triage_level=r.triage_level,
                is_life_threat=r.is_life_threat,
                people_affected=r.people_affected,
                has_media=r.has_media,
                misinfo_signals=list(r.misinfo_signals or []),
                incident_id=r.incident_id,
                status=r.status,
                processing_ms=r.processing_ms,
                source=r.source,
                version=r.version,
            )
        )
    return out


async def _dispatch_state(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, str]]:
    """Estado y agencia del despacho más reciente no cancelado de cada incidente."""
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Dispatch.incident_id, Dispatch.status, Agency.name)
            .join(Agency, Agency.id == Dispatch.agency_id)
            .where(Dispatch.incident_id.in_(ids), Dispatch.status != DispatchStatus.cancelado)
            .order_by(Dispatch.incident_id, Dispatch.created_at)
        )
    ).all()
    state: dict[uuid.UUID, tuple[str, str]] = {}
    for incident_id, status, agency in rows:
        prev = state.get(incident_id)
        # Un despacho activo prevalece sobre uno finalizado (p. ej. refuerzo en curso).
        if prev is None or status in ACTIVE_DISPATCH or prev[0] == DispatchStatus.finalizado:
            state[incident_id] = (status.value, agency)
    return state


async def incidents_out(
    session: AsyncSession, incidents: Sequence[Incident]
) -> list[IncidentSummary]:
    coords = await _coords(session, Incident, [i.id for i in incidents])
    dispatch = await _dispatch_state(session, [i.id for i in incidents])
    threshold = datetime.now(UTC) - timedelta(minutes=get_settings().unattended_alert_min)
    out = []
    for i in incidents:
        lat, lon = coords.get(i.id, (None, None))
        status, agency = dispatch.get(i.id, ("sin_despacho", None))
        unattended = (
            i.is_life_threat
            and status == "sin_despacho"
            and i.status in OPEN_FOR_DISPATCH
            and i.created_at is not None
            and i.created_at < threshold
        )
        out.append(
            IncidentSummary(
                id=i.id,
                lat=lat,
                lon=lon,
                category=i.category,
                triage_level=i.triage_level,
                is_life_threat=i.is_life_threat,
                report_count=i.report_count,
                independent_sources=i.independent_sources,
                people_affected=i.people_affected,
                trust_score=i.trust_score,
                trust_label=i.trust_label,
                status=i.status,
                first_seen=i.first_seen,
                last_seen=i.last_seen,
                manzana_id=i.manzana_id,
                barrio=i.barrio,
                geo_precision=i.geo_precision,
                updated_at=i.updated_at,
                source=i.source,
                dispatch_status=status,  # type: ignore[arg-type]
                assigned_agency=agency,
                unattended=bool(unattended),
            )
        )
    return out


def events_out(events: Sequence[ReportEvent]) -> list[ReportEventOut]:
    return [
        ReportEventOut(
            id=e.id,
            report_id=e.report_id,
            incident_id=e.incident_id,
            actor_role=e.actor_role,
            action=e.action,
            payload=e.payload,
            at=e.at,
        )
        for e in events
    ]


async def resources_out(session: AsyncSession, resources: Sequence[Resource]) -> list[ResourceOut]:
    if not resources:
        return []
    ids = [r.id for r in resources]
    rows = (
        await session.execute(
            select(
                Resource.id,
                func.ST_Y(Resource.last_geom),
                func.ST_X(Resource.last_geom),
                Agency.code,
            )
            .join(Agency, Agency.id == Resource.agency_id)
            .where(Resource.id.in_(ids))
        )
    ).all()
    info = {rid: (lat, lon, code) for rid, lat, lon, code in rows}
    active = dict(
        (
            await session.execute(
                select(Dispatch.resource_id, Dispatch.id).where(
                    Dispatch.resource_id.in_(ids), Dispatch.status.in_(list(ACTIVE_DISPATCH))
                )
            )
        ).all()
    )
    out = []
    for r in resources:
        lat, lon, code = info[r.id]
        out.append(
            ResourceOut(
                id=r.id,
                code=r.code,
                label=r.label,
                type=r.type,
                status=r.status,
                agency_id=r.agency_id,
                agency_code=code,
                lat=lat,
                lon=lon,
                last_seen_at=r.last_seen_at,
                active_dispatch_id=active.get(r.id),
                source=r.source,
            )
        )
    return out


async def dispatches_out(
    session: AsyncSession, dispatches: Sequence[Dispatch]
) -> list[DispatchOut]:
    if not dispatches:
        return []
    resources = {
        r.id: r
        for r in (
            await session.execute(
                select(Resource).where(Resource.id.in_({d.resource_id for d in dispatches}))
            )
        ).scalars()
    }
    resource_out = {r.id: r for r in await resources_out(session, list(resources.values()))}
    agencies = {
        a.id: a
        for a in (
            await session.execute(
                select(Agency).where(Agency.id.in_({d.agency_id for d in dispatches}))
            )
        ).scalars()
    }
    return [
        DispatchOut(
            id=d.id,
            incident_id=d.incident_id,
            resource=resource_out[d.resource_id],
            agency=AgencyRef(
                id=d.agency_id, code=agencies[d.agency_id].code, name=agencies[d.agency_id].name
            ),
            emre_function=d.emre_function,
            suggested=d.suggested,
            is_reinforcement=d.is_reinforcement,
            justification=d.justification,
            status=d.status,
            eta_at=d.eta_at,
            distance_m=d.distance_m,
            created_by_role=d.created_by_role,
            created_at=d.created_at,
            arrived_at=d.arrived_at,
            closed_at=d.closed_at,
            close_note=d.close_note,
            source=d.source,
        )
        for d in dispatches
    ]


async def tracks_out(session: AsyncSession, tracks: Sequence[ResourceTrack]) -> list[TrackOut]:
    if not tracks:
        return []
    rows = (
        await session.execute(
            select(
                ResourceTrack.id, func.ST_Y(ResourceTrack.geom), func.ST_X(ResourceTrack.geom)
            ).where(ResourceTrack.id.in_([t.id for t in tracks]))
        )
    ).all()
    coords = {tid: (lat, lon) for tid, lat, lon in rows}
    return [
        TrackOut(
            id=t.id,
            resource_id=t.resource_id,
            dispatch_id=t.dispatch_id,
            kind=t.kind,
            origin=t.origin,
            lat=coords[t.id][0],
            lon=coords[t.id][1],
            at=t.at,
            source=t.source,
        )
        for t in tracks
    ]
