"""Alertas oficiales (specs/002 US2; contracts/rest-api.md §Alertas). Solo el COE las emite."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.alert_gateway import gateway
from app.adapters.event_bus import bus
from app.auth import require_role
from app.core.alerts import (
    AlertError,
    AreaSpec,
    approve_alert,
    cancel_alert,
    create_alert,
    reject_alert,
    update_alert,
)
from app.db import get_session
from app.domain import AlertChannel, AlertStatus, Role
from app.models import Alert, AlertDelivery, AlertEvent
from app.schemas import (
    AlertAreaIn,
    AlertCancelIn,
    AlertDecisionIn,
    AlertEventList,
    AlertEventOut,
    AlertIn,
    AlertList,
    AlertOut,
    AlertPatchIn,
    DeliveryOut,
)

router = APIRouter(prefix="/alerts", tags=["alertas"])

EDITORS = (Role.operador_pmu, Role.coe)
ANY_ROLE = require_role()  # cualquier token válido; el dominio decide (403 coe_only)


def _http(err: AlertError) -> HTTPException:
    return HTTPException(err.status, detail={"detail": err.message, "code": err.code, **err.extra})


def _spec(area: AlertAreaIn | None) -> AreaSpec | None:
    if area is None:
        return None
    if area.circle:
        return AreaSpec(lat=area.circle.lat, lon=area.circle.lon, radius_m=area.circle.radius_m)
    return AreaSpec(barrios=tuple(area.barrios or ()))


async def _areas(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Any]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Alert.id, func.ST_AsGeoJSON(Alert.area, 6)).where(Alert.id.in_(ids))
        )
    ).all()
    return {aid: json.loads(geo) for aid, geo in rows}


async def alerts_out(session: AsyncSession, alerts: Sequence[Alert]) -> list[AlertOut]:
    ids = [a.id for a in alerts]
    areas = await _areas(session, ids)
    deliveries: dict[uuid.UUID, list[DeliveryOut]] = {i: [] for i in ids}
    if ids:
        for d in (
            await session.execute(
                select(AlertDelivery)
                .where(AlertDelivery.alert_id.in_(ids))
                .order_by(AlertDelivery.at)
            )
        ).scalars():
            deliveries[d.alert_id].append(
                DeliveryOut(
                    channel=AlertChannel(d.channel),
                    recipients_count=d.recipients_count,
                    at=d.at,
                    source=d.source,
                )
            )
    return [
        AlertOut(
            id=a.id,
            type=a.type,
            status=a.status,
            version=a.version,
            area=areas.get(a.id, {}),
            area_barrios=list(a.area_barrios or []),
            area_circle=a.area_circle,
            message=a.message,
            channels=[AlertChannel(c) for c in a.channels],
            misinfo_signals=list(a.misinfo_signals or []),
            origin_incident_id=a.origin_incident_id,
            origin_manzana_id=a.origin_manzana_id,
            created_by_role=a.created_by_role,
            approved_by_role=a.approved_by_role,
            created_at=a.created_at,
            updated_at=a.updated_at,
            emitted_at=a.emitted_at,
            closed_at=a.closed_at,
            close_reason=a.close_reason,
            deliveries=deliveries[a.id],
            source=a.source,
        )
        for a in alerts
    ]


def _publish(alert: Alert, role: Role) -> None:
    bus.publish(
        "alert.changed",
        {
            "alert_id": str(alert.id),
            "status": alert.status.value,
            "version": alert.version,
            "type": alert.type.value,
            "actor_role": role.value,
            "at": datetime.now(UTC).isoformat(),
        },
    )


async def _get(session: AsyncSession, alert_id: uuid.UUID) -> Alert:
    alert = (
        await session.execute(select(Alert).where(Alert.id == alert_id).with_for_update())
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(404, detail={"detail": "Alerta no existe", "code": "not_found"})
    return alert


async def _single(session: AsyncSession, alert: Alert) -> AlertOut:
    return (await alerts_out(session, [alert]))[0]


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def post_alert(
    body: AlertIn,
    role: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    try:
        alert = await create_alert(
            session,
            type_=body.type,
            area=_spec(body.area) or AreaSpec(),
            message=body.message,
            channels=[c.value for c in body.channels],
            origin_incident_id=body.origin_incident_id,
            origin_manzana_id=body.origin_manzana_id,
            confirm_misinformation=body.confirm_misinformation,
            actor=role,
        )
    except AlertError as err:
        await session.rollback()
        raise _http(err) from err
    _publish(alert, role)
    return await _single(session, alert)


@router.get("", response_model=AlertList)
async def list_alerts(
    status_: AlertStatus | None = Query(default=None, alias="status"),
    _: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> AlertList:
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(200)
    if status_:
        stmt = stmt.where(Alert.status == status_)
    alerts = list((await session.execute(stmt)).scalars())
    return AlertList(items=await alerts_out(session, alerts), cutoff_at=datetime.now(UTC))


@router.get("/active")
async def active_alerts(
    role: Role = Depends(require_role(Role.publico, Role.operador_pmu, Role.coe, Role.agencia)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Alertas emitidas como GeoJSON. El público solo ve las del mapa público y sin detalles."""
    alerts = list(
        (
            await session.execute(
                select(Alert)
                .where(Alert.status == AlertStatus.emitida)
                .order_by(Alert.emitted_at.desc())
            )
        ).scalars()
    )
    if role == Role.publico:
        alerts = [a for a in alerts if AlertChannel.mapa_publico in a.channels]
    areas = await _areas(session, [a.id for a in alerts])
    features = []
    for a in alerts:
        props: dict[str, Any] = {
            "id": str(a.id),
            "type": a.type.value,
            "message": a.message,
            "emitted_at": a.emitted_at.isoformat() if a.emitted_at else None,
            "source": a.source,
        }
        if role != Role.publico:
            props["channels"] = list(a.channels)
            props["version"] = a.version
        features.append({"type": "Feature", "geometry": areas.get(a.id), "properties": props})
    return {
        "type": "FeatureCollection",
        "features": features,
        "cutoff_at": datetime.now(UTC).isoformat(),
    }


@router.get("/{alert_id}/events", response_model=AlertEventList)
async def alert_events(
    alert_id: uuid.UUID,
    _: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> AlertEventList:
    events = (
        await session.execute(
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(AlertEvent.at, AlertEvent.created_at)
        )
    ).scalars()
    return AlertEventList(
        items=[
            AlertEventOut(
                id=e.id,
                action=e.action,
                actor_role=e.actor_role,
                alert_version=e.alert_version,
                payload=e.payload,
                at=e.at,
            )
            for e in events
        ]
    )


@router.patch("/{alert_id}", response_model=AlertOut)
async def patch_alert(
    alert_id: uuid.UUID,
    body: AlertPatchIn,
    role: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    alert = await _get(session, alert_id)
    try:
        alert = await update_alert(
            session,
            alert,
            version=body.version,
            type_=body.type,
            area=_spec(body.area),
            message=body.message,
            channels=[c.value for c in body.channels] if body.channels is not None else None,
            confirm_misinformation=body.confirm_misinformation,
            actor=role,
        )
    except AlertError as err:
        await session.rollback()
        raise _http(err) from err
    _publish(alert, role)
    return await _single(session, alert)


@router.post("/{alert_id}/approve", response_model=AlertOut)
async def approve(
    alert_id: uuid.UUID,
    body: AlertDecisionIn,
    role: Role = Depends(ANY_ROLE),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    alert = await _get(session, alert_id)
    try:
        await approve_alert(
            session, alert, version=body.version, actor=role, gateway=gateway, now=datetime.now(UTC)
        )
    except AlertError as err:
        await session.rollback()
        raise _http(err) from err
    _publish(alert, role)
    return await _single(session, alert)


@router.post("/{alert_id}/reject", response_model=AlertOut)
async def reject(
    alert_id: uuid.UUID,
    body: AlertDecisionIn,
    role: Role = Depends(ANY_ROLE),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    alert = await _get(session, alert_id)
    try:
        await reject_alert(
            session,
            alert,
            version=body.version,
            reason=body.reason,
            actor=role,
            now=datetime.now(UTC),
        )
    except AlertError as err:
        await session.rollback()
        raise _http(err) from err
    _publish(alert, role)
    return await _single(session, alert)


@router.post("/{alert_id}/cancel", response_model=AlertOut)
async def cancel(
    alert_id: uuid.UUID,
    body: AlertCancelIn,
    role: Role = Depends(ANY_ROLE),
    session: AsyncSession = Depends(get_session),
) -> AlertOut:
    alert = await _get(session, alert_id)
    try:
        await cancel_alert(session, alert, reason=body.reason, actor=role, now=datetime.now(UTC))
    except AlertError as err:
        await session.rollback()
        raise _http(err) from err
    _publish(alert, role)
    return await _single(session, alert)
