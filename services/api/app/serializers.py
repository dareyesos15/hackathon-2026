"""Conversión de modelos ORM a esquemas de salida (incluye lat/lon desde PostGIS)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, Report, ReportEvent
from app.schemas import IncidentSummary, ReportEventOut, ReportOut


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


async def incidents_out(
    session: AsyncSession, incidents: Sequence[Incident]
) -> list[IncidentSummary]:
    coords = await _coords(session, Incident, [i.id for i in incidents])
    out = []
    for i in incidents:
        lat, lon = coords.get(i.id, (None, None))
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
