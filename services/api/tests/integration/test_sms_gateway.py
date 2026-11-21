"""Pasarela SMS Android: webhooks firmados que entran como reportes SMS, sin duplicar."""

import json
import time
import uuid
from collections.abc import Iterator

import httpx
import pytest

from app.config import get_settings
from app.core.sms_gateway import sign

KEY = "clave-de-prueba-pasarela"


@pytest.fixture
def gateway_key() -> Iterator[str]:
    settings = get_settings()
    before = settings.sms_gateway_signing_key
    settings.sms_gateway_signing_key = KEY
    yield KEY
    settings.sms_gateway_signing_key = before


def _webhook(message: str, message_id: str, event: str = "sms:received") -> bytes:
    return json.dumps(
        {
            "deviceId": "celular-pmu",
            "event": event,
            "id": str(uuid.uuid4()),
            "webhookId": "dacora",
            "payload": {
                "messageId": message_id,
                "message": message,
                "sender": "+573001234567",
                "recipient": None,
                "simNumber": 1,
                "receivedAt": "2026-11-21T10:00:00.000-05:00",
            },
        }
    ).encode()


async def _post(client: httpx.AsyncClient, body: bytes, key: str = KEY) -> httpx.Response:
    ts = str(int(time.time()))
    return await client.post(
        "/ingest/sms-gateway",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": ts,
            "X-Signature": sign(key, body, ts),
        },
    )


async def test_gateway_is_off_without_key(client: httpx.AsyncClient) -> None:
    resp = await _post(client, _webhook("hola", "m-0"))
    assert resp.status_code == 503


async def test_free_text_sms_becomes_a_report_once(
    client: httpx.AsyncClient, gateway_key: str
) -> None:
    message_id = f"m-{uuid.uuid4()}"
    body = _webhook("Se cayo una casa en Milan, hay 2 personas atrapadas", message_id)
    first = await _post(client, body)
    assert first.status_code == 201, first.text
    report = first.json()["report"]
    assert report["channel"] == "sms"
    assert report["is_life_threat"]
    # El número del remitente nunca queda en el texto ni en la respuesta.
    assert "3001234567" not in first.text

    retry = await _post(client, body)  # la app reintenta con el mismo messageId
    assert retry.status_code == 200
    assert retry.json()["report"]["id"] == report["id"]


async def test_forged_or_foreign_webhooks_are_rejected(
    client: httpx.AsyncClient, gateway_key: str
) -> None:
    body = _webhook("reporte falso", f"m-{uuid.uuid4()}")
    assert (await _post(client, body, key="otra-clave")).status_code == 401
    other = _webhook("ping", f"m-{uuid.uuid4()}", event="system:ping")
    assert (await _post(client, other)).status_code == 204
