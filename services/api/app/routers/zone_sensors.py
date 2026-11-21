"""Sensor de zonas inseguras (specs/004; patente UNAL NC2025/0015763). Datos SIMULADOS.

`POST /sensors/zones/{id}/readings` es el punto de integración con el dispositivo real: el
simulador (`app/adapters/zone_sensor.py`) usa la misma función `process_reading`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.core.pipeline import Engine, refresh_trust
from app.core.zone_sensor import (
    CONFIRM_RADIUS_M,
    CONFIRMABLE_CATEGORIES,
    Cone,
    Reading,
    classify,
    cone_polygon,
)
from app.db import get_session
from app.domain import IncidentStatus, Role, ZoneDetector, ZoneEventKind
from app.models import Incident, RfidBadge, ZoneSensor, ZoneSensorEvent
from app.routers.ingest import get_engine
from app.serializers import incidents_out
from app.zone_schemas import (
    ZoneEventList,
    ZoneEventOut,
    ZoneLastEvent,
    ZoneReadingIn,
    ZoneReadingResult,
    ZoneSensorIn,
    ZoneSensorList,
    ZoneSensorOut,
)

router = APIRouter(prefix="/sensors/zones", tags=["sensor de zonas inseguras"])

READERS = (Role.operador_pmu, Role.coe, Role.agencia, Role.inspector)
OPERATORS = (Role.operador_pmu, Role.coe)
DEVICE = (Role.operador_pmu, Role.coe, Role.sistema, Role.admin)
SOURCE = "SIMULADO · patente NC2025/0015763"
ACTIVE = (IncidentStatus.abierto, IncidentStatus.en_revision, IncidentStatus.verificado)


def _error(code: int, detail: str, kind: str) -> HTTPException:
    return HTTPException(code, detail={"detail": detail, "code": kind})


async def _badges(session: AsyncSession) -> dict[str, str]:
    rows = await session.execute(select(RfidBadge.tag, RfidBadge.agency_code))
    return {tag: agency for tag, agency in rows.all()}


async def events_out(
    session: AsyncSession, events: Sequence[ZoneSensorEvent]
) -> list[ZoneEventOut]:
    ids = {e.sensor_id for e in events}
    sensors = (
        {
            s.id: s
            for s in (
                await session.execute(select(ZoneSensor).where(ZoneSensor.id.in_(ids)))
            ).scalars()
        }
        if ids
        else {}
    )
    badges = await _badges(session)
    return [
        ZoneEventOut(
            id=e.id,
            sensor_id=e.sensor_id,
            sensor_code=sensors[e.sensor_id].code,
            sensor_label=sensors[e.sensor_id].label,
            kind=e.kind,
            detector=e.detector,
            distance_m=e.distance_m,
            bearing_deg=e.bearing_deg,
            rfid_tag=e.rfid_tag,
            badge_agency=badges.get(e.rfid_tag or ""),
            authorized=e.authorized,
            battery_pct=e.battery_pct,
            at=e.at,
            acknowledged_at=e.acknowledged_at,
            acknowledged_by=e.acknowledged_by,
            source=e.source,
        )
        for e in events
    ]


async def sensors_out(session: AsyncSession, sensors: Sequence[ZoneSensor]) -> list[ZoneSensorOut]:
    ids = [s.id for s in sensors]
    if not ids:
        return []
    alarms = dict(
        (
            await session.execute(
                select(ZoneSensorEvent.sensor_id, func.count())
                .where(
                    ZoneSensorEvent.sensor_id.in_(ids),
                    ZoneSensorEvent.kind.in_([ZoneEventKind.intrusion, ZoneEventKind.manipulacion]),
                    ZoneSensorEvent.acknowledged_at.is_(None),
                )
                .group_by(ZoneSensorEvent.sensor_id)
            )
        ).all()
    )
    ranked = (
        select(
            ZoneSensorEvent.sensor_id,
            ZoneSensorEvent.kind,
            ZoneSensorEvent.at,
            func.row_number()
            .over(partition_by=ZoneSensorEvent.sensor_id, order_by=ZoneSensorEvent.at.desc())
            .label("rn"),
        )
        .where(ZoneSensorEvent.sensor_id.in_(ids))
        .subquery()
    )
    last = {
        sid: ZoneLastEvent(kind=kind, at=at)
        for sid, kind, at in (
            await session.execute(
                select(ranked.c.sensor_id, ranked.c.kind, ranked.c.at).where(ranked.c.rn == 1)
            )
        ).all()
    }
    out: list[ZoneSensorOut] = []
    for s in sensors:
        point = to_shape(s.geom)
        cone = Cone(s.range_m, s.half_angle_deg)
        out.append(
            ZoneSensorOut(
                id=s.id,
                code=s.code,
                label=s.label,
                lat=point.y,
                lon=point.x,
                heading_deg=s.heading_deg,
                range_m=s.range_m,
                half_angle_deg=s.half_angle_deg,
                incident_id=s.incident_id,
                status=s.status,
                battery_pct=s.battery_pct,
                last_seen_at=s.last_seen_at,
                open_alarms=int(alarms.get(s.id, 0)),
                last_event=last.get(s.id),
                cone=cone_polygon(point.y, point.x, s.heading_deg, cone),
                source=s.source,
            )
        )
    return out


async def _confirm_incidents(
    session: AsyncSession, engine: Engine, sensor: ZoneSensor
) -> list[Incident]:
    """Recalcula el trust de los incidentes estructurales cercanos (señal sensor_campo)."""
    incidents = list(
        (
            await session.execute(
                select(Incident).where(
                    Incident.status.in_(ACTIVE),
                    Incident.category.in_(list(CONFIRMABLE_CATEGORIES)),
                    Incident.centroid.is_not(None),
                    func.ST_DWithin(
                        func.Geography(Incident.centroid),
                        func.Geography(
                            select(ZoneSensor.geom)
                            .where(ZoneSensor.id == sensor.id)
                            .scalar_subquery()
                        ),
                        CONFIRM_RADIUS_M,
                    ),
                )
            )
        ).scalars()
    )
    for incident in incidents:
        await refresh_trust(session, engine, incident)
    return incidents


async def process_reading(
    session: AsyncSession,
    engine: Engine,
    sensor: ZoneSensor,
    body: ZoneReadingIn,
    now: datetime,
) -> ZoneReadingResult:
    """Clasifica una lectura, guarda sus eventos y publica en vivo. Misma ruta real y simulada."""
    badges = await _badges(session)
    reading = Reading(
        ultrasonic_m=body.ultrasonic_m,
        infrared=body.infrared,
        bearing_deg=body.bearing_deg,
        rfid_tag=body.rfid_tag,
        battery_pct=body.battery_pct,
        tamper=body.tamper,
    )
    sensor.battery_pct = body.battery_pct
    sensor.last_seen_at = now
    events: list[ZoneSensorEvent] = []
    for c in classify(reading, Cone(sensor.range_m, sensor.half_angle_deg), frozenset(badges)):
        event = ZoneSensorEvent(
            sensor_id=sensor.id,
            kind=c.kind,
            detector=c.detector,
            distance_m=round(c.distance_m, 1) if c.distance_m is not None else None,
            bearing_deg=round(body.bearing_deg, 1) if c.detector else None,
            rfid_tag=(body.rfid_tag or "").strip().upper() or None if c.detector else None,
            authorized=c.authorized,
            battery_pct=body.battery_pct,
            at=now,
            source=SOURCE,
        )
        session.add(event)
        events.append(event)
    await session.flush()
    confirmed: list[Incident] = []
    if any(e.kind == ZoneEventKind.intrusion and e.detector == ZoneDetector.ambos for e in events):
        confirmed = await _confirm_incidents(session, engine, sensor)
    await session.commit()
    out = await events_out(session, events)
    for item in out:
        bus.publish("zone.event", item.model_dump(mode="json"))
    for summary in await incidents_out(session, confirmed):
        bus.publish("incident.upserted", summary.model_dump(mode="json"))
    return ZoneReadingResult(events=out, confirmed_incidents=[i.id for i in confirmed])


async def _sensor(session: AsyncSession, sensor_id: uuid.UUID) -> ZoneSensor:
    sensor = await session.get(ZoneSensor, sensor_id)
    if sensor is None:
        raise _error(404, "Sensor no existe", "not_found")
    return sensor


@router.get("", response_model=ZoneSensorList)
async def list_sensors(
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> ZoneSensorList:
    sensors = list((await session.execute(select(ZoneSensor).order_by(ZoneSensor.code))).scalars())
    return ZoneSensorList(items=await sensors_out(session, sensors), cutoff_at=datetime.now(UTC))


@router.post("", response_model=ZoneSensorOut, status_code=status.HTTP_201_CREATED)
async def install_sensor(
    body: ZoneSensorIn,
    _: Role = Depends(require_role(*OPERATORS)),
    session: AsyncSession = Depends(get_session),
) -> ZoneSensorOut:
    """Instala un sensor (SIMULADO) en un incidente o en un punto."""
    lat, lon = body.lat, body.lon
    if body.incident_id is not None:
        row = (
            await session.execute(
                select(func.ST_Y(Incident.centroid), func.ST_X(Incident.centroid)).where(
                    Incident.id == body.incident_id
                )
            )
        ).first()
        if row is None or row[0] is None:
            raise _error(422, "El incidente no existe o no tiene ubicación", "incident_location")
        lat, lon = row
    if lat is None or lon is None:
        raise _error(422, "Indique un incidente o las coordenadas", "location_required")
    count = await session.scalar(select(func.count()).select_from(ZoneSensor)) or 0
    sensor = ZoneSensor(
        code=f"ZI-{count + 1:03d}",
        label=body.label,
        geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
        heading_deg=body.heading_deg,
        range_m=body.range_m,
        half_angle_deg=body.half_angle_deg,
        incident_id=body.incident_id,
        battery_pct=100,
        last_seen_at=datetime.now(UTC),
        source=SOURCE,
    )
    session.add(sensor)
    await session.commit()
    out = (await sensors_out(session, [sensor]))[0]
    bus.publish("zone.sensor", out.model_dump(mode="json"))
    return out


@router.post("/{sensor_id}/readings", response_model=ZoneReadingResult)
async def post_reading(
    sensor_id: uuid.UUID,
    body: ZoneReadingIn,
    _: Role = Depends(require_role(*DEVICE)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ZoneReadingResult:
    """Lectura del dispositivo (ultrasonido, infrarrojo, RFID, batería)."""
    sensor = await _sensor(session, sensor_id)
    return await process_reading(session, engine, sensor, body, datetime.now(UTC))


@router.get("/events", response_model=ZoneEventList)
async def list_events(
    since: datetime | None = None,
    only_alarms: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> ZoneEventList:
    stmt = select(ZoneSensorEvent).order_by(ZoneSensorEvent.at.desc()).limit(limit)
    if since:
        stmt = stmt.where(ZoneSensorEvent.at > since)
    if only_alarms:
        stmt = stmt.where(
            ZoneSensorEvent.kind.in_([ZoneEventKind.intrusion, ZoneEventKind.manipulacion]),
            ZoneSensorEvent.acknowledged_at.is_(None),
        )
    events = list((await session.execute(stmt)).scalars())
    return ZoneEventList(items=await events_out(session, events), cutoff_at=datetime.now(UTC))


@router.post("/events/{event_id}/ack", response_model=ZoneEventOut)
async def acknowledge(
    event_id: uuid.UUID,
    role: Role = Depends(require_role(*OPERATORS, Role.agencia)),
    session: AsyncSession = Depends(get_session),
) -> ZoneEventOut:
    """Marca una alarma como atendida (queda el rol y la hora)."""
    event = await session.get(ZoneSensorEvent, event_id)
    if event is None:
        raise _error(404, "Evento no existe", "not_found")
    if event.acknowledged_at is None:
        event.acknowledged_at = datetime.now(UTC)
        event.acknowledged_by = role.value
        await session.commit()
    out = (await events_out(session, [event]))[0]
    bus.publish("zone.event", out.model_dump(mode="json"))
    return out
