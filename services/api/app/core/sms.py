"""Parser del SMS compacto: `DACORA <CÓDIGO> <LUGAR> <N_PERSONAS> <texto>` (sms-format.md)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.text import normalize
from app.domain import Category

PREFIX = "dacora"
MAX_LENGTH = 160

CODES: dict[str, Category] = {
    "ATR": Category.personas_atrapadas,
    "HER": Category.heridos,
    "COL": Category.colapso_estructura,
    "DAN": Category.dano_estructural,
    "INC": Category.incendio,
    "GAS": Category.fuga_gas,
    "DES": Category.deslizamiento,
    "VIA": Category.via_bloqueada,
    "SER": Category.servicios_caidos,
    "ALB": Category.necesidad_albergue,
    "AYU": Category.necesidad_ayuda,
    "DSP": Category.persona_desaparecida,
}

_COORDS_RE = re.compile(r"^(-?\d{1,2}\.\d+),(-?\d{1,3}\.\d+)$")


@dataclass(frozen=True)
class ParsedSms:
    has_prefix: bool
    category: Category | None
    place_token: str | None
    coords: tuple[float, float] | None
    people: int | None
    text: str
    too_long: bool


def parse_sms(body: str) -> ParsedSms:
    """Nunca falla: un SMS sin formato se devuelve como texto libre (va a revisión)."""
    raw = body.strip()
    too_long = len(raw) > MAX_LENGTH
    tokens = raw.split()
    if not tokens or tokens[0].lower() != PREFIX:
        return ParsedSms(False, None, None, None, None, raw, too_long)

    rest = tokens[1:]
    category: Category | None = None
    if rest:
        category = CODES.get(rest[0].upper())
        rest = rest[1:]

    place_token: str | None = None
    coords: tuple[float, float] | None = None
    if rest:
        match = _COORDS_RE.match(rest[0])
        if match:
            coords = (float(match.group(1)), float(match.group(2)))
        else:
            place_token = normalize(rest[0].replace("_", " "), expand=False) or None
        rest = rest[1:]

    people: int | None = None
    if rest and rest[0].isdigit():
        people = int(rest[0])
        rest = rest[1:]

    return ParsedSms(True, category, place_token, coords, people, " ".join(rest), too_long)
