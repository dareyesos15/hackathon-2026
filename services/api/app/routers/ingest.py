"""Ingesta multicanal: /ingest/report, /ingest/sms, /ingest/batch (contracts/rest-api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.adapters.hazard import hazard_provider
from app.auth import require_role
from app.config import get_settings
from app.core.pipeline import Engine, IncomingReport, PipelineResult, process_report
from app.core.privacy import reporter_hash
from app.core.sms import parse_sms
from app.db import SessionLocal, get_session
from app.domain import Channel, GeoPrecision, Role
from app.schemas import BatchIn, BatchItemResult, BatchOut, ReportIn, ReportResult, SmsIn
from app.serializers import incidents_out, reports_out
from app.state import get_state

router = APIRouter(prefix="/ingest", tags=["ingesta"])

SMS_NAMESPACE = uuid.UUID("5d1c6f8e-1c1e-4b7a-9a52-6a0c2a1d0a11")
CITIZEN_CHANNELS = {Channel.pwa}
OPERATOR_CHANNELS = {
    Channel.pwa,
    Channel.entity,
    Channel.whatsapp,
    Channel.call_123,
    Channel.scraping,
    Channel.lora,
    Channel.sms,
}


def get_engine() -> Engine:
    state = get_state()
    return Engine(get_settings(), state.gazetteer, state.similarity, hazard_provider, bus)


async def to_result(session: AsyncSession, result: PipelineResult) -> ReportResult:
    report = (await reports_out(session, [result.report]))[0]
    incident = (await incidents_out(session, [result.incident]))[0]
    if result.created:
        bus.publish(
            "report.created",
            {
                "report_id": str(report.id),
                "incident_id": str(incident.id),
                "triage_level": report.triage_level.value,
                "is_life_threat": report.is_life_threat,
            },
        )
        bus.publish("incident.upserted", incident.model_dump(mode="json"))
    return ReportResult(
        report=report,
        incident=incident,
        joined_existing_incident=result.joined_existing_incident,
        created=result.created,
        processing_ms=result.processing_ms,
    )


def incoming_from(body: ReportIn, role: Role) -> IncomingReport:
    allowed = CITIZEN_CHANNELS if role == Role.ciudadano else OPERATOR_CHANNELS
    if body.channel not in allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"detail": "Canal no permitido para su rol", "code": "forbidden_channel"},
        )
    if body.channel == Channel.pwa and not body.consent:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Debe aceptar el aviso de privacidad antes de reportar",
                "code": "consent_required",
            },
        )
    loc = body.location
    return IncomingReport(
        client_uuid=body.client_uuid,
        channel=body.channel,
        text=body.text,
        received_at=datetime.now(UTC),
        occurred_at=body.occurred_at,
        category_hint=body.category_hint,
        lat=loc.lat if loc else None,
        lon=loc.lon if loc else None,
        gps_precision=GeoPrecision(loc.precision) if loc else GeoPrecision.gps,
        barrio=body.barrio,
        people_affected=body.people_affected,
        has_media=body.has_media,
        reporter_contact=body.reporter_contact,
    )


@router.post(
    "/report",
    response_model=ReportResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": ReportResult, "description": "Ya existía (idempotente)"}},
)
async def ingest_report(
    body: ReportIn,
    response: Response,
    role: Role = Depends(require_role(Role.ciudadano, Role.operador_pmu)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ReportResult:
    result = await process_report(session, engine, incoming_from(body, role))
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return await to_result(session, result)


@router.post(
    "/sms",
    response_model=ReportResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": ReportResult, "description": "Ya existía (idempotente)"}},
)
async def ingest_sms(
    body: SmsIn,
    response: Response,
    _: Role = Depends(require_role(Role.operador_pmu)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ReportResult:
    received_at = body.received_at or datetime.now(UTC)
    sms = parse_sms(body.body)
    sender = reporter_hash(body.from_, salt=engine.settings.pii_salt) or ""
    minute = received_at.strftime("%Y%m%d%H%M")
    client_uuid = uuid.uuid5(SMS_NAMESPACE, f"{sender}|{body.body}|{minute}")
    incoming = IncomingReport(
        client_uuid=client_uuid,
        channel=Channel.sms,
        text=body.body,
        classify_text=sms.text if sms.has_prefix else body.body,
        received_at=received_at,
        occurred_at=received_at,
        category_hint=sms.category,
        lat=sms.coords[0] if sms.coords else None,
        lon=sms.coords[1] if sms.coords else None,
        place_token=sms.place_token,
        people_affected=sms.people,
        reporter_contact=body.from_,
        location_text=sms.place_token,
    )
    result = await process_report(session, engine, incoming)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return await to_result(session, result)


@router.post("/batch", response_model=BatchOut)
async def ingest_batch(
    body: BatchIn,
    role: Role = Depends(require_role(Role.ciudadano, Role.operador_pmu)),
    engine: Engine = Depends(get_engine),
) -> BatchOut:
    """Sincronización del outbox de la PWA. Un ítem inválido no hace fallar el lote."""
    results: list[BatchItemResult] = []
    for item in body.items:
        async with SessionLocal() as session:
            try:
                result = await process_report(session, engine, incoming_from(item, role))
                await to_result(session, result)
                results.append(
                    BatchItemResult(
                        client_uuid=item.client_uuid,
                        status="created" if result.created else "duplicate",
                        report_id=result.report.id,
                    )
                )
            except HTTPException as exc:
                await session.rollback()
                detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
                results.append(
                    BatchItemResult(
                        client_uuid=item.client_uuid, status="error", error=detail.get("code")
                    )
                )
    return BatchOut(results=results)
