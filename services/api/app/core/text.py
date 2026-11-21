"""Normalización de texto en español colombiano (minúsculas, sin tildes, abreviaturas de SMS)."""

from __future__ import annotations

import re
import unicodedata

ABBREVIATIONS: dict[str, str] = {
    "cra": "carrera",
    "kra": "carrera",
    "cr": "carrera",
    "kr": "carrera",
    "cll": "calle",
    "cl": "calle",
    "av": "avenida",
    "avda": "avenida",
    "edif": "edificio",
    "q": "que",
    "k": "que",
    "xq": "porque",
    "pq": "porque",
    "x": "por",
    "tb": "tambien",
    "tmb": "tambien",
    "hosp": "hospital",
    "urg": "urgente",
    "pers": "personas",
    "ppl": "personas",
}

_MARKER_RE = re.compile(r"\[(?:NOMBRE|TEL|CC|CORREO|PLACA)\]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize(text: str, *, expand: bool = True) -> str:
    """Texto comparable: minúsculas, sin tildes ni signos, abreviaturas expandidas."""
    text = _MARKER_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub(" ", strip_accents(text.lower())).strip()
    if not expand:
        return " ".join(text.split())
    return " ".join(ABBREVIATIONS.get(tok, tok) for tok in text.split())
