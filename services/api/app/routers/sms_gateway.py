"""Webhook de la pasarela SMS Android (SMS Gateway for Android, evento `sms:received`).

No usa token de rol: la autenticidad la da la firma HMAC de cada webhook (app/core/sms_gateway.py).
Los reintentos de la app traen el mismo `messageId`, así que nunca duplican el reporte.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.pipeline import Engine
from app.core.sms_gateway import verify
from app.db import get_session
from app.routers.ingest import SMS_NAMESPACE, get_engine, process_sms, to_result
from app.schemas import ReportResult

router = APIRouter(prefix="/ingest", tags=["ingesta"])


class GatewaySms(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    message_id: str = Field(alias="messageId", min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=1000)
    sender: str = Field(min_length=3, max_length=32)
    received_at: datetime | None = Field(default=None, alias="receivedAt")


class GatewayWebhook(BaseModel):
    """Sobre del webhook: `event`, `payload` y datos del dispositivo (se ignoran)."""

    model_config = ConfigDict(extra="ignore")

    event: str
    payload: dict[str, object] = Field(default_factory=dict)


def _error(code: int, detail: str, kind: str) -> HTTPException:
    return HTTPException(code, detail={"detail": detail, "code": kind})


@router.post(
    "/sms-gateway",
    response_model=ReportResult,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "SMS ya recibido (reintento de la pasarela)"},
        204: {"description": "Evento distinto de sms:received: se ignora"},
        401: {"description": "Firma inválida o vencida"},
        503: {"description": "Pasarela SMS no configurada"},
    },
)
async def sms_gateway_webhook(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> ReportResult | Response:
    """Recibe un SMS reenviado por el celular Android con SIM y lo procesa como reporte SMS."""
    key = get_settings().sms_gateway_signing_key
    if not key:
        raise _error(503, "Pasarela SMS no configurada (SMS_GATEWAY_SIGNING_KEY)", "not_configured")
    raw = await request.body()
    problem = verify(
        key, raw, request.headers.get("X-Timestamp"), request.headers.get("X-Signature")
    )
    if problem:
        raise _error(401, problem, "bad_signature")
    try:
        webhook = GatewayWebhook.model_validate_json(raw)
        if webhook.event != "sms:received":
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        sms = GatewaySms.model_validate(webhook.payload)
    except ValidationError as err:
        raise _error(
            422, f"Webhook con formato inesperado: {err.errors()[:1]}", "bad_payload"
        ) from err
    received_at = sms.received_at or datetime.now(UTC)
    client_uuid = uuid.uuid5(SMS_NAMESPACE, f"gateway|{sms.message_id}")
    result = await process_sms(session, engine, sms.sender, sms.message, received_at, client_uuid)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return await to_result(session, result)
