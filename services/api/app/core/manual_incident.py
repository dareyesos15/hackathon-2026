"""Creación manual de incidentes por el PMU/COE (sin reportes ciudadanos).

El incidente nace con un registro de origen (`reports`, canal `entity`, fuente "PMU · registro
manual") para conservar el mismo modelo: bitácora, trust score, mapa y reporte final. No pasa por
la deduplicación: lo crea una persona a propósito. Como lo crea una persona, nace verificado.
La descripción se redacta antes de guardarse (Ley 1581).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import locate
from app.core.mass_alert import MassAlertError
from app.core.nlp import classify
from app.core.pipeline import Engine, _manzana_for, refresh_trust
from app.core.privacy import redact
from app.domain import (
    Category,
    Channel,
    GeoPrecision,
    IncidentStatus,
    MassAlertStatus,
    ReportAction,
    ReportStatus,
    Role,
    TriageLevel,
)
from app.models import Incident, MassAlert, Report, ReportEvent

MANUAL_SOURCE = "PMU · registro manual"


@dataclass(frozen=True)
class ManualIncident:
    category: Category
    description: str
    triage_level: TriageLevel | None = None
    barrio: str | None = None
    lat: float | None = None
    lon: float | None = None
    people_affected: int | None = None
    mass_alert_id: uuid.UUID | None = None


async def create_manual_incident(
    session: AsyncSession, engine: Engine, data: ManualIncident, actor: Role
) -> Incident:
    if data.mass_alert_id is not None:
        alert = await session.get(MassAlert, data.mass_alert_id)
        if alert is None or alert.status != MassAlertStatus.activa:
            raise MassAlertError(
                "alert_closed", "Solo se crean incidentes en alertas masivas activas", 409
            )
    redacted = redact(data.description)
    cls = classify(redacted.text, hint=data.category, people=data.people_affected)
    triage = data.triage_level or cls.triage_level
    loc = locate(
        gazetteer=engine.gazetteer,
        lat=data.lat,
        lon=data.lon,
        gps_precision=GeoPrecision.gps,
        barrio=data.barrio,
        text=redacted.text,
    )
    if not loc.has_point:
        raise MassAlertError(
            "location_required", "Indique un barrio conocido o un punto dentro de Manizales", 422
        )
    manzana_id: str | None = None
    barrio = loc.barrio
    if loc.lat is not None and loc.lon is not None:
        manzana_id, manzana_barrio = await _manzana_for(session, loc.lat, loc.lon)
        barrio = (manzana_barrio or barrio) if loc.precision == GeoPrecision.gps else barrio
        barrio = barrio or manzana_barrio

    now = datetime.now(UTC)
    incident = Incident(
        id=uuid.uuid4(),
        category=data.category,
        triage_level=triage,
        is_life_threat=cls.is_life_threat,
        first_seen=now,
        last_seen=now,
        status=IncidentStatus.verificado,
        geo_precision=loc.precision,
        mass_alert_id=data.mass_alert_id,
        pending_assignment=False,
        source=MANUAL_SOURCE,
    )
    session.add(incident)
    await session.flush()
    report = Report(
        id=uuid.uuid4(),
        client_uuid=uuid.uuid4(),
        channel=Channel.entity,
        received_at=now,
        occurred_at=now,
        text_redacted=redacted.text[:2000],
        location_text=data.barrio,
        geom=WKTElement(f"POINT({loc.lon} {loc.lat})", srid=4326) if loc.has_point else None,
        geo_precision=loc.precision,
        manzana_id=manzana_id,
        barrio=barrio,
        category=data.category,
        severity=cls.severity,
        triage_level=triage,
        is_life_threat=cls.is_life_threat,
        people_affected=data.people_affected,
        has_media=False,
        reporter_hash=None,
        misinfo_signals=cls.misinfo_signals,
        incident_id=incident.id,
        status=ReportStatus.verificado,
        source=MANUAL_SOURCE,
    )
    session.add(report)
    await session.flush()
    await refresh_trust(session, engine, incident)
    session.add(
        ReportEvent(
            report_id=report.id,
            incident_id=incident.id,
            actor_role=actor,
            action=ReportAction.crear_manual,
            payload={
                "categoria": data.category.value,
                "triaje": triage.value,
                "sesion": str(data.mass_alert_id) if data.mass_alert_id else "ordinaria",
                "redacciones": redacted.kinds,
            },
            source=MANUAL_SOURCE,
        )
    )
    await session.commit()
    await session.refresh(incident)
    return incident
