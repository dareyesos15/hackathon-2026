"""Lógica pura de recuperación (specs/003): predio único, hash de hogar y reglas de ayudas."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import datetime, timedelta

from app.domain import AidType, DamageLevel, InspectionColor

# Abreviaturas de vías en Manizales → forma canónica.
_STREET_ALIASES = {
    "cra": "carrera",
    "kra": "carrera",
    "kr": "carrera",
    "cr": "carrera",
    "carrera": "carrera",
    "cl": "calle",
    "cll": "calle",
    "calle": "calle",
    "av": "avenida",
    "avda": "avenida",
    "avenida": "avenida",
    "dg": "diagonal",
    "diagonal": "diagonal",
    "tv": "transversal",
    "trans": "transversal",
    "transversal": "transversal",
}
_NOISE = {"no", "n", "numero", "num", "nro"}

# Daños compatibles con cada color (NSR-10, semáforo de habitabilidad).
COLOR_DAMAGE: dict[InspectionColor, frozenset[DamageLevel]] = {
    InspectionColor.verde: frozenset({DamageLevel.menor}),
    InspectionColor.amarillo: frozenset({DamageLevel.menor, DamageLevel.mediano_uso_restringido}),
    InspectionColor.rojo: frozenset(
        {DamageLevel.mediano_uso_restringido, DamageLevel.mayor, DamageLevel.colapso}
    ),
}

# Ventana en la que la misma ayuda al mismo hogar se considera duplicada.
AID_DUPLICATE_WINDOW: dict[AidType, timedelta] = {
    AidType.subsidio_arriendo: timedelta(days=30),
    AidType.kit: timedelta(days=30),
    AidType.mercado: timedelta(days=7),
    AidType.albergue: timedelta(days=30),
}


def _ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


def normalize_address(address: str) -> str:
    """'Cra. 23 # 45-10' y 'carrera 23 45 10' → 'carrera 23 45 10'."""
    tokens = re.findall(r"[a-z]+|\d+[a-z]?", _ascii(address))
    out: list[str] = []
    for token in tokens:
        if token in _NOISE:
            continue
        out.append(_STREET_ALIASES.get(token, token))
    return " ".join(out)


def property_key(*, cadastral_code: str | None, manzana_id: str | None, address: str | None) -> str:
    """Identificador único de predio: código catastral o manzana + dirección normalizada."""
    if cadastral_code and cadastral_code.strip():
        return "CAT:" + re.sub(r"[^0-9A-Z]", "", cadastral_code.upper())
    if not manzana_id or not address or not normalize_address(address):
        raise ValueError("Indique el código catastral o la manzana y la dirección del predio")
    return f"{manzana_id}:{normalize_address(address)}"


def normalize_document(document: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", document).upper()


def household_hash(document: str, *, salt: str) -> str:
    """HMAC-SHA256(sal, documento normalizado). El documento nunca se guarda."""
    normalized = normalize_document(document)
    if len(normalized) < 5:
        raise ValueError("Documento del jefe de hogar inválido")
    return hmac.new(salt.encode(), f"hogar:{normalized}".encode(), hashlib.sha256).hexdigest()


def consistent(color: InspectionColor, damage: DamageLevel) -> bool:
    return damage in COLOR_DAMAGE[color]


def is_duplicate_aid(aid_type: AidType, previous: list[datetime], now: datetime) -> bool:
    window = AID_DUPLICATE_WINDOW[aid_type]
    return any(now - at < window for at in previous)


def suppress(value: int, k: int) -> int | None:
    """Supresión k-anónima para cifras públicas (k ≥ 5)."""
    return value if value >= k else None
