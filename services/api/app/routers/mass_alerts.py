"""Alerta masiva de toda la ciudad: activar, consultar y reporte final.

Activarla abre una sesión de operación propia: los incidentes nuevos quedan en ella y el tablero
del PMU muestra triaje, cascada y zonas solo de esa sesión. Se resuelve sola cuando todos sus
incidentes se cierran y entonces queda el reporte final (core/mass_alert.py).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.core.alerts import AlertError, AreaSpec, barrio_shapes, create_alert
from app.core.mass_alert import active_mass_alert, build_report, check_resolution, progress
from app.db import get_session
from app.domain import AlertType, MassAlertEvent, MassAlertStatus, Role
from app.mass_alert_schemas import MassAlertIn, MassAlertList, MassAlertOut, MassAlertReport
from app.models import MassAlert

router = APIRouter(prefix="/mass-alerts", tags=["alerta masiva"])

EDITORS = (Role.operador_pmu, Role.coe)

OFFICIAL_TYPE = {
    MassAlertEvent.sismo: AlertType.sismo_replica,
    MassAlertEvent.deslizamientos: AlertType.deslizamiento,
    MassAlertEvent.inundacion: AlertType.evacuacion,
    MassAlertEvent.ceniza_volcanica: AlertType.informacion_general,
    MassAlertEvent.incendio_estructural: AlertType.evacuacion,
    MassAlertEvent.otro: AlertType.informacion_general,
}

DEFAULT_MESSAGE = {
    MassAlertEvent.sismo: (
        "Sismo en Manizales. Salga a zona abierta, no use ascensores y reporte daños o personas "
        "atrapadas en Dacora o al 123."
    ),
    MassAlertEvent.deslizamientos: (
        "Deslizamientos en Manizales. Aléjese de laderas y taludes y reporte en Dacora o al 123."
    ),
    MassAlertEvent.inundacion: (
        "Inundaciones en Manizales. Evite cauces y zonas bajas y reporte en Dacora o al 123."
    ),
    MassAlertEvent.ceniza_volcanica: (
        "Caída de ceniza en Manizales. Use tapabocas, cubra el agua y siga canales oficiales."
    ),
    MassAlertEvent.incendio_estructural: (
        "Incendios en Manizales. Evacúe si hay humo y reporte en Dacora o al 123."
    ),
    MassAlertEvent.otro: (
        "Emergencia en Manizales. Siga instrucciones oficiales y reporte en Dacora."
    ),
}


async def mass_alert_out(session: AsyncSession, alert: MassAlert) -> MassAlertOut:
    total, closed = await progress(session, alert.id)
    return MassAlertOut(
        id=alert.id,
        title=alert.title,
        event_type=alert.event_type,
        description=alert.description,
        status=alert.status,
        started_at=alert.started_at,
        resolved_at=alert.resolved_at,
        created_by_role=alert.created_by_role,
        official_alert_id=alert.official_alert_id,
        incidents_total=total,
        incidents_closed=closed,
        has_report=alert.final_report is not None,
    )


def _publish(alert: MassAlert) -> None:
    bus.publish(
        "mass_alert.changed",
        {
            "mass_alert_id": str(alert.id),
            "status": alert.status.value,
            "at": datetime.now(UTC).isoformat(),
        },
    )


async def resolve_and_publish(
    session: AsyncSession, mass_alert_ids: Sequence[uuid.UUID | None]
) -> None:
    """Tras cerrar incidentes o despachos: resuelve la alerta si ya no queda nada abierto."""
    ids = [m for m in mass_alert_ids if m is not None]
    if not ids:
        return
    for alert in await check_resolution(session, ids):
        _publish(alert)
    # Progreso (cerrados / total) para la barra de la sesión.
    for mid in set(ids):
        bus.publish("mass_alert.changed", {"mass_alert_id": str(mid), "status": "progreso"})


async def _get(session: AsyncSession, mass_alert_id: uuid.UUID) -> MassAlert:
    alert = await session.get(MassAlert, mass_alert_id)
    if alert is None:
        raise HTTPException(404, detail={"detail": "Alerta masiva no existe", "code": "not_found"})
    return alert


@router.get("", response_model=MassAlertList)
async def list_mass_alerts(
    _: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> MassAlertList:
    alerts = list(
        (
            await session.execute(select(MassAlert).order_by(MassAlert.started_at.desc()).limit(50))
        ).scalars()
    )
    items = [await mass_alert_out(session, a) for a in alerts]
    active = next((i for i in items if i.status == MassAlertStatus.activa), None)
    return MassAlertList(items=items, active=active)


@router.post("", response_model=MassAlertOut, status_code=status.HTTP_201_CREATED)
async def post_mass_alert(
    body: MassAlertIn,
    role: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> MassAlertOut:
    """Activa la alerta masiva. Solo puede haber una activa a la vez (409)."""
    if await active_mass_alert(session) is not None:
        raise HTTPException(
            409,
            detail={
                "detail": "Ya hay una alerta masiva activa; se resuelve cuando se cierren sus "
                "incidentes",
                "code": "mass_alert_active",
            },
        )
    official_id: uuid.UUID | None = None
    if body.official_alert:
        try:
            official = await create_alert(
                session,
                type_=OFFICIAL_TYPE[body.event_type],
                area=AreaSpec(barrios=tuple(sorted(barrio_shapes()))),
                message=body.message or DEFAULT_MESSAGE[body.event_type],
                channels=[c.value for c in body.channels] or ["tablero"],
                origin_incident_id=None,
                origin_manzana_id=None,
                confirm_misinformation=True,
                actor=role,
            )
        except AlertError as err:
            await session.rollback()
            raise HTTPException(
                err.status, detail={"detail": err.message, "code": err.code, **err.extra}
            ) from err
        official_id = official.id
        bus.publish(
            "alert.changed",
            {
                "alert_id": str(official.id),
                "status": official.status.value,
                "version": official.version,
                "type": official.type.value,
                "actor_role": role.value,
                "at": datetime.now(UTC).isoformat(),
            },
        )
    alert = MassAlert(
        title=body.title.strip(),
        event_type=body.event_type,
        description=(body.description or "").strip() or None,
        status=MassAlertStatus.activa,
        started_at=datetime.now(UTC),
        created_by_role=role,
        official_alert_id=official_id,
        source="tablero PMU",
        version=1,
    )
    session.add(alert)
    try:
        await session.commit()
    except IntegrityError as err:  # carrera: otra alerta masiva se activó al tiempo
        await session.rollback()
        raise HTTPException(
            409, detail={"detail": "Ya hay una alerta masiva activa", "code": "mass_alert_active"}
        ) from err
    _publish(alert)
    return await mass_alert_out(session, alert)


@router.get("/{mass_alert_id}", response_model=MassAlertOut)
async def get_mass_alert(
    mass_alert_id: uuid.UUID,
    _: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> MassAlertOut:
    return await mass_alert_out(session, await _get(session, mass_alert_id))


@router.get("/{mass_alert_id}/report", response_model=MassAlertReport)
async def get_mass_alert_report(
    mass_alert_id: uuid.UUID,
    _: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> MassAlertReport:
    """Reporte final guardado al resolverse; mientras siga activa, uno preliminar al corte."""
    alert = await _get(session, mass_alert_id)
    report = alert.final_report or await build_report(session, alert)
    return MassAlertReport(mass_alert=await mass_alert_out(session, alert), report=report)
