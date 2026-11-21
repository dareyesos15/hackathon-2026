"""Lluvia SIMULADA y capa de efectos en cascada (specs/002 US3; contracts/rest-api.md §Lluvia)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.adapters.hazard import hazard_provider
from app.adapters.terrain import terrain_provider
from app.auth import require_role
from app.config import get_settings
from app.core import cascade
from app.db import get_session
from app.domain import CascadeLevel, Role
from app.models import RainReading
from app.schemas import RainIn, RainOut

router = APIRouter(tags=["cascada"])

READERS = (Role.operador_pmu, Role.coe)
LEVEL_RANK = {
    CascadeLevel.bajo: 0,
    CascadeLevel.medio: 1,
    CascadeLevel.alto: 2,
    CascadeLevel.muy_alto: 3,
}
THROTTLE_S = 3.0
_last_notice = 0.0


def notify_invalidated(reason: str) -> None:
    """Invalida la caché y avisa al tablero, como máximo un evento cada 3 s."""
    global _last_notice
    cascade.invalidate()
    now = time.monotonic()
    if now - _last_notice < THROTTLE_S:
        return
    _last_notice = now
    bus.publish(
        "cascade.invalidated", {"reason": reason, "cutoff_at": datetime.now(UTC).isoformat()}
    )


def _rain_out(r: RainReading) -> RainOut:
    return RainOut(
        id=r.id, station_code=r.station_code, mm_3h=float(r.mm_3h), at=r.at, source=r.source
    )


@router.post("/sensors/rain", response_model=RainOut, status_code=status.HTTP_201_CREATED)
async def post_rain(
    body: RainIn,
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> RainOut:
    reading = RainReading(
        station_code=body.station_code,
        mm_3h=body.mm_3h,
        at=datetime.now(UTC),
        source="SIMULADO",
    )
    session.add(reading)
    await session.commit()
    global _last_notice
    _last_notice = 0.0  # un cambio de lluvia siempre se avisa
    notify_invalidated("lluvia")
    return _rain_out(reading)


@router.get("/sensors/rain/latest", response_model=RainOut | None)
async def get_latest_rain(
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> RainOut | None:
    reading = await cascade.latest_rain(session)
    return _rain_out(reading) if reading else None


def _public(feature: dict[str, Any], k: int) -> dict[str, Any]:
    """Para el público, menos de k reportes cercanos no se cuentan (k-anonimato, principio I)."""
    props = dict(feature["properties"])
    breakdown = {name: dict(part) for name, part in props["breakdown"].items()}
    reports = breakdown["reportes_cercanos"]
    if reports.pop("n", 0) < k:
        reports["detalle"] = f"menos de {k} reportes cercanos (dato protegido)"
    props["breakdown"] = breakdown
    return {**feature, "properties": props}


@router.get("/map/cascade")
async def cascade_layer(
    min_level: CascadeLevel | None = Query(default=None),
    role: Role = Depends(require_role()),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GeoJSON de manzanas con nivel de riesgo de cascada y desglose (SIMULADO).

    Visible para todos los roles, también el público: es una predicción agregada por manzana
    para que la ciudadanía sepa qué puede pasar. Solo es una sugerencia (FR-031).
    """
    settings = get_settings()
    layer = await cascade.compute(session, settings.cascade, terrain_provider, hazard_provider)
    features = layer["features"]
    if min_level is not None:
        floor = LEVEL_RANK[min_level]
        features = [
            f for f in features if LEVEL_RANK[CascadeLevel(f["properties"]["level"])] >= floor
        ]
    if role == Role.publico:
        features = [_public(f, settings.k_anonymity) for f in features]
    return {**layer, "features": features}
