"""Pasarela SMS en un celular Android (app SMS Gateway for Android, modo servidor local).

El celular con SIM recibe los SMS de la ciudadanía y los reenvía a Dacora como webhook
`sms:received`. Sin internet: por cable USB con `adb reverse` (el celular ve a Dacora en
`http://127.0.0.1`, única dirección que la app admite sin HTTPS) o por Wi-Fi con HTTPS.

Seguridad: cada webhook llega firmado. Firma = HMAC-SHA256(clave, cuerpo crudo + X-Timestamp),
en hexadecimal en `X-Signature`. Se rechazan firmas inválidas y marcas de tiempo a más de
5 minutos (evita repetir un mensaje capturado). Ver docs/pasarela_sms.md.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

MAX_SKEW_S = 300


def sign(key: str, raw_body: bytes, timestamp: str) -> str:
    return hmac.new(key.encode(), raw_body + timestamp.encode(), hashlib.sha256).hexdigest()


def verify(
    key: str,
    raw_body: bytes,
    timestamp: str | None,
    signature: str | None,
    now: datetime | None = None,
) -> str | None:
    """`None` si el webhook es auténtico; si no, el motivo del rechazo."""
    if not timestamp or not signature:
        return "Faltan las cabeceras X-Timestamp o X-Signature"
    try:
        ts = int(timestamp)
    except ValueError:
        return "X-Timestamp inválido"
    current = (now or datetime.now(UTC)).timestamp()
    if abs(current - ts) > MAX_SKEW_S:
        return "Mensaje fuera de la ventana de 5 minutos"
    if not hmac.compare_digest(sign(key, raw_body, timestamp), signature.strip().lower()):
        return "Firma inválida"
    return None
