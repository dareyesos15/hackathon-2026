"""Filtro Habeas Data (principio I, FR-006/FR-007). Autoridad de redacción del sistema.

Espejo en TypeScript: apps/web/lib/redact.ts (mismos casos en data/fixtures/pii_cases.json).
Orden: correo → teléfono → cédula → placa → nombres.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field

_LETTER = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celular colombiano: 3XX XXX XXXX, con o sin +57 / 57, separadores espacio o guion.
PHONE_RE = re.compile(r"(?<![\d.])(?:\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?![\d.])")
# Cédula: 6–10 dígitos seguidos, o con puntos de miles (1.053.123.456 / 75.123.456).
CC_RE = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3}){2,3}|\d{6,10})(?![\d.,]?\d)")
# Placa: ABC123 / ABC 123 (carro), ABC12D (moto). Solo mayúsculas para no tocar texto común.
PLATE_RE = re.compile(rf"(?<![{_LETTER}0-9])[A-Z]{{3}}[\s-]?\d{{2}}[0-9A-Z](?![{_LETTER}0-9])")

_FAMILY = (
    "mamá|mama|papá|papa|hijo|hija|esposo|esposa|hermano|hermana|abuelo|abuela|"
    "tío|tio|tía|tia|novio|novia"
)
# Tras estos disparadores, cualquier palabra (hasta 3) es nombre, salvo palabras vacías.
TRIGGER_ANY_RE = re.compile(rf"(?<![{_LETTER}])(?:me llamo|mi nombre es)\s+", re.IGNORECASE)
# Tras estos, solo palabras con mayúscula inicial (evita "soy de Milán").
TRIGGER_CAP_RE = re.compile(
    rf"(?<![{_LETTER}])(?:soy|mi (?:{_FAMILY})(?: se llama)?)\s+", re.IGNORECASE
)
WORD_RE = re.compile(rf"[{_LETTER}]+")

STOPWORDS = frozenset(
    [
        "y",
        "e",
        "o",
        "u",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "en",
        "estoy",
        "esta",
        "está",
        "con",
        "que",
        "por",
        "mi",
        "a",
        "al",
        "soy",
        "tengo",
        "vivo",
        "desde",
        "para",
        "se",
        "no",
    ]
)

MARKERS = ("[NOMBRE]", "[TEL]", "[CC]", "[CORREO]", "[PLACA]")


@dataclass(frozen=True)
class Redaction:
    text: str
    kinds: list[str] = field(default_factory=list)


def _sub(pattern: re.Pattern[str], marker: str, text: str, kinds: list[str]) -> str:
    new, count = pattern.subn(marker, text)
    if count:
        kinds.append(marker.strip("[]"))
    return new


def _name_span(text: str, start: int, require_capital: bool) -> int:
    """Devuelve el fin del nombre que empieza en `start` (o `start` si no hay nombre)."""
    end = start
    pos = start
    for _ in range(3):
        match = WORD_RE.match(text, pos)
        if not match:
            break
        word = match.group(0)
        if word.lower() in STOPWORDS:
            break
        if require_capital and not word[0].isupper():
            break
        end = match.end()
        # Siguiente palabra solo si está separada por exactamente un espacio.
        if text[end : end + 1] == " ":
            pos = end + 1
        else:
            break
    return end


def _redact_names(text: str, kinds: list[str]) -> str:
    spans: list[tuple[int, int]] = []
    for pattern, require_capital in ((TRIGGER_ANY_RE, False), (TRIGGER_CAP_RE, True)):
        for match in pattern.finditer(text):
            end = _name_span(text, match.end(), require_capital)
            if end > match.end():
                spans.append((match.end(), end))
    if not spans:
        return text
    kinds.append("NOMBRE")
    out: list[str] = []
    last = 0
    for start, end in sorted(set(spans)):
        if start < last:
            continue
        out.append(text[last:start])
        out.append("[NOMBRE]")
        last = end
    out.append(text[last:])
    return "".join(out)


def redact(text: str | None) -> Redaction:
    """Reemplaza datos personales por marcadores. Idempotente."""
    if not text:
        return Redaction(text="")
    kinds: list[str] = []
    out = _sub(EMAIL_RE, "[CORREO]", text, kinds)
    out = _sub(PHONE_RE, "[TEL]", out, kinds)
    out = _sub(CC_RE, "[CC]", out, kinds)
    out = _sub(PLATE_RE, "[PLACA]", out, kinds)
    out = _redact_names(out, kinds)
    return Redaction(text=out, kinds=kinds)


def contains_pii(text: str) -> bool:
    """Verificación usada por las pruebas sobre el escenario (SC-004)."""
    return bool(EMAIL_RE.search(text) or PHONE_RE.search(text) or CC_RE.search(text))


def _normalize_contact(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if digits:
        if len(digits) == 12 and digits.startswith("57"):
            digits = digits[2:]
        return digits
    return value.strip().lower()


def reporter_hash(contact: str | None, *, salt: str) -> str | None:
    """HMAC-SHA256(sal, dato normalizado). Permite cruzar remitentes sin conocerlos."""
    if not contact or not contact.strip():
        return None
    return hmac.new(salt.encode(), _normalize_contact(contact).encode(), hashlib.sha256).hexdigest()
