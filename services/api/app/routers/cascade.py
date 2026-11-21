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


@router.get("/map/cascade")
async def cascade_layer(
    min_level: CascadeLevel | None = Query(default=None),
    _: Role = Depends(require_role(*READERS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GeoJSON de manzanas con nivel de riesgo de cascada y desglose (SIMULADO)."""
    layer = await cascade.compute(
        session, get_settings().cascade, terrain_provider, hazard_provider
    )
    if min_level is None:
        return layer
    floor = LEVEL_RANK[min_level]
    return {
        **layer,
        "features": [
            f
            for f in layer["features"]
            if LEVEL_RANK[CascadeLevel(f["properties"]["level"])] >= floor
        ],
    }
