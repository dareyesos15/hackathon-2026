"""Firma de los webhooks de la pasarela SMS (HMAC-SHA256 del cuerpo + marca de tiempo)."""

from datetime import UTC, datetime

from app.core.sms_gateway import sign, verify

KEY = "clave-de-prueba"
BODY = b'{"event":"sms:received"}'
NOW = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
TS = str(int(NOW.timestamp()))


def test_valid_signature_is_accepted() -> None:
    assert verify(KEY, BODY, TS, sign(KEY, BODY, TS), now=NOW) is None


def test_tampered_body_or_wrong_key_is_rejected() -> None:
    good = sign(KEY, BODY, TS)
    assert verify(KEY, BODY + b" ", TS, good, now=NOW) == "Firma inválida"
    assert verify("otra", BODY, TS, good, now=NOW) == "Firma inválida"


def test_old_or_missing_timestamps_are_rejected() -> None:
    old = str(int(NOW.timestamp()) - 600)
    assert "5 minutos" in (verify(KEY, BODY, old, sign(KEY, BODY, old), now=NOW) or "")
    assert verify(KEY, BODY, None, "x", now=NOW)
    assert verify(KEY, BODY, "abc", "x", now=NOW) == "X-Timestamp inválido"
