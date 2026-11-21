"""Utilidades exclusivas de la demo (datos SIMULADOS). Desactivables con DEMO_MODE=false."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.config import get_settings
from app.core import cascade
from app.db import get_session
from app.domain import Role

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_demo_data(
    _: Role = Depends(require_role(Role.operador_pmu)),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Borra reportes, incidentes, despachos, alertas, lluvia, bitácora y métricas.

    Conserva la geografía. Solo existe en modo demo: en producción los reportes son solo-agregar.
    """
    if not get_settings().demo_mode:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"detail": "Reinicio deshabilitado fuera de modo demo", "code": "forbidden"},
        )
    await session.execute(
        text(
            "TRUNCATE report_events, resource_tracks, dispatches, alert_events, alert_deliveries,"
            " alerts, rain_readings, reports, incidents, metrics_snapshots CASCADE"
        )
    )
    # El catálogo se conserva; los recursos vuelven a su base (research R16).
    await session.execute(
        text(
            "UPDATE resources SET status = 'disponible', last_geom = base_geom, last_seen_at = NULL"
        )
    )
    await session.commit()
    cascade.invalidate()
    bus.publish("demo.reset", {})
