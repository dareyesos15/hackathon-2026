"""Pipeline del motor: redactar → clasificar → ubicar → agrupar → puntuar → registrar → publicar.

Reglas no negociables (constitución I y III):
- Nada se persiste sin redactar.
- El actor `sistema` solo lleva reportes a `en_revision`; nunca a `descartado` ni `duplicado`.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import EventBus
from app.adapters.hazard import HazardProvider
from app.config import Settings
from app.core.dedup import ReportCtx, choose_incident, find_candidates, recompute_incident
from app.core.geo import Gazetteer, locate
from app.core.nlp import classify
from app.core.privacy import redact, reporter_hash
from app.core.similarity import SimilarityProvider
from app.core.trust import ReportSignals, compute_trust
from app.domain import (
    Category,
    Channel,
    GeoPrecision,
    IncidentStatus,
    ReportAction,
    ReportStatus,
    Role,
)
from app.models import Incident, Manzana, Report, ReportEvent

DEDUP_LOCK_KEY = 0xDAC0A  # bloqueo asesor: agrupación serializada (research R10)
MAX_FUTURE_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class IncomingReport:
    client_uuid: uuid.UUID
    channel: Channel
    text: str
    received_at: datetime
    occurred_at: datetime | None = None
    classify_text: str | None = None  # p. ej. el cuerpo del SMS sin encabezado
    category_hint: Category | None = None
    lat: float | None = None
    lon: float | None = None
    gps_precision: GeoPrecision = GeoPrecision.gps
    barrio: str | None = None
    place_token: str | None = None
    people_affected: int | None = None
    has_media: bool = False
    reporter_contact: str | None = None
    location_text: str | None = None
    source: str = "SIMULADO"


@dataclass
class PipelineResult:
    report: Report
    incident: Incident
    joined_existing_incident: bool
    created: bool
    processing_ms: int
    events: list[ReportEvent] = field(default_factory=list)


@dataclass(frozen=True)
class Engine:
    settings: Settings
    gazetteer: Gazetteer
    similarity: SimilarityProvider
    hazard: HazardProvider
    bus: EventBus


async def _manzana_for(
    session: AsyncSession, lat: float, lon: float
) -> tuple[str, str] | tuple[None, None]:
    """(id, barrio) de la manzana que contiene el punto."""
    point = WKTElement(f"POINT({lon} {lat})", srid=4326)
    row = (
        await session.execute(
            select(Manzana.id, Manzana.barrio).where(func.ST_Contains(Manzana.geom, point)).limit(1)
        )
    ).first()
    return (row[0], row[1]) if row else (None, None)


async def refresh_trust(session: AsyncSession, engine: Engine, incident: Incident) -> None:
    """Recalcula agregados y trust score del incidente (FR-020)."""
    reports = await recompute_incident(session, incident)
    consistency = engine.hazard.consistency(incident.manzana_id, incident.category.value)
    result = compute_trust(
        [
            ReportSignals(r.channel, r.geo_precision, r.has_media, tuple(r.misinfo_signals))
            for r in reports
        ],
        incident.independent_sources,
        consistency,
        engine.settings.trust,
    )
    incident.trust_score = result.score
    incident.trust_label = result.label
    incident.trust_breakdown = result.breakdown
    incident.updated_at = datetime.now(UTC)


async def process_report(
    session: AsyncSession, engine: Engine, incoming: IncomingReport
) -> PipelineResult:
    start = time.perf_counter()
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": DEDUP_LOCK_KEY})

    # Idempotencia por identificador del cliente (FR-005).
    existing = await session.scalar(
        select(Report).where(Report.client_uuid == incoming.client_uuid)
    )
    if existing is not None:
        incident = await session.get(Incident, existing.incident_id)
        await session.commit()
        assert incident is not None
        return PipelineResult(existing, incident, False, False, existing.processing_ms)

    # 1. Habeas Data: redactar antes de cualquier otra cosa.
    redacted = redact(incoming.text)
    location_text = redact(incoming.location_text).text if incoming.location_text else None
    hashed = reporter_hash(incoming.reporter_contact, salt=engine.settings.pii_salt)
    classify_source = redact(incoming.classify_text or incoming.text).text

    # 2. Clasificación y triaje.
    cls = classify(classify_source, hint=incoming.category_hint, people=incoming.people_affected)

    # 3. Ubicación.
    loc = locate(
        gazetteer=engine.gazetteer,
        lat=incoming.lat,
        lon=incoming.lon,
        gps_precision=incoming.gps_precision,
        barrio=incoming.barrio,
        place_token=incoming.place_token,
        text=classify_source,
    )
    manzana_id: str | None = None
    barrio = loc.barrio
    if loc.lat is not None and loc.lon is not None:
        manzana_id, manzana_barrio = await _manzana_for(session, loc.lat, loc.lon)
        # Con GPS manda el punto: el barrio es el de la manzana donde cae, no el del texto.
        if loc.precision == GeoPrecision.gps and manzana_barrio:
            barrio = manzana_barrio
        else:
            barrio = barrio or manzana_barrio

    occurred_at = incoming.occurred_at or incoming.received_at
    if occurred_at > incoming.received_at + MAX_FUTURE_SKEW:
        occurred_at = incoming.received_at

    # 4. Agrupación.
    ctx = ReportCtx(
        category=cls.category,
        lat=loc.lat,
        lon=loc.lon,
        precision=loc.precision,
        occurred_at=occurred_at,
        text=redacted.text,
        reporter_hash=hashed,
    )
    candidates = await find_candidates(session, ctx, engine.settings.dedup)
    match = choose_incident(ctx, candidates, engine.similarity, engine.settings.dedup)

    if match is not None:
        incident = await session.get(Incident, match.incident_id)
        assert incident is not None
    else:
        incident = Incident(
            id=uuid.uuid4(),
            category=cls.category,
            triage_level=cls.triage_level,
            is_life_threat=cls.is_life_threat,
            first_seen=occurred_at,
            last_seen=occurred_at,
            status=IncidentStatus.abierto,
            geo_precision=loc.precision,
            source=incoming.source,
        )
        session.add(incident)
        await session.flush()

    report = Report(
        id=uuid.uuid4(),
        client_uuid=incoming.client_uuid,
        channel=incoming.channel,
        received_at=incoming.received_at,
        occurred_at=occurred_at,
        text_redacted=redacted.text[:2000],
        location_text=location_text,
        geom=WKTElement(f"POINT({loc.lon} {loc.lat})", srid=4326) if loc.has_point else None,
        geo_precision=loc.precision,
        manzana_id=manzana_id,
        barrio=barrio,
        category=cls.category,
        severity=cls.severity,
        triage_level=cls.triage_level,
        is_life_threat=cls.is_life_threat,
        people_affected=incoming.people_affected,
        has_media=incoming.has_media,
        reporter_hash=hashed,
        misinfo_signals=cls.misinfo_signals,
        incident_id=incident.id,
        # El sistema solo puede dejar el reporte en revisión (FR-013).
        status=ReportStatus.en_revision,
        source=incoming.source,
    )
    session.add(report)
    await session.flush()

    # 5. Agregados y trust score.
    await refresh_trust(session, engine, incident)
    if incident.report_count > 1 and incident.status == IncidentStatus.abierto:
        incident.status = IncidentStatus.en_revision

    # 6. Bitácora solo-agregar.
    events = [
        ReportEvent(
            report_id=report.id,
            incident_id=incident.id,
            actor_role=Role.sistema,
            action=ReportAction.ingerido,
            payload={
                "canal": incoming.channel.value,
                "categoria": cls.category.value,
                "triaje": cls.triage_level.value,
                "redacciones": redacted.kinds,
                "senales_desinformacion": cls.misinfo_signals,
            },
            source=incoming.source,
        )
    ]
    if match is not None:
        events.append(
            ReportEvent(
                report_id=report.id,
                incident_id=incident.id,
                actor_role=Role.sistema,
                action=ReportAction.agrupado,
                payload={
                    "similitud": round(match.similarity, 3),
                    "distancia_m": round(match.distance_m) if match.distance_m else None,
                },
                source=incoming.source,
            )
        )
    session.add_all(events)

    processing_ms = int((time.perf_counter() - start) * 1000)
    report.processing_ms = processing_ms
    await session.commit()

    return PipelineResult(report, incident, match is not None, True, processing_ms, events)
