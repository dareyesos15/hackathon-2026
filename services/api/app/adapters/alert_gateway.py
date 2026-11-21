"""Difusión de alertas emitidas (research R10). Interfaz `AlertGateway` (principio VI).

`SimulatedGateway`: tablero y mapa público se difunden por el bus de eventos y por
`GET /alerts/active`; el SMS a cuadrillas solo se registra con el número de destinatarios
(recursos en camino o en sitio dentro del área y recursos con base en el área). Nunca guarda
números ni identidades (principio I). Un gateway SMS real sería otra implementación.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AlertChannel, ResourceStatus
from app.models import Alert, AlertDelivery, Resource


class AlertGateway(Protocol):
    async def deliver(
        self, session: AsyncSession, alert: Alert, now: datetime
    ) -> list[AlertDelivery]: ...


class SimulatedGateway:
    async def _field_recipients(self, session: AsyncSession, alert: Alert) -> int:
        area = select(Alert.area).where(Alert.id == alert.id).scalar_subquery()
        count = await session.scalar(
            select(func.count())
            .select_from(Resource)
            .where(
                or_(
                    Resource.status.in_([ResourceStatus.en_camino, ResourceStatus.en_sitio])
                    & func.ST_Within(Resource.last_geom, area),
                    func.ST_Within(Resource.base_geom, area),
                )
            )
        )
        return int(count or 0)

    async def deliver(
        self, session: AsyncSession, alert: Alert, now: datetime
    ) -> list[AlertDelivery]:
        deliveries = []
        for channel in alert.channels:
            recipients = (
                await self._field_recipients(session, alert)
                if channel == AlertChannel.sms_cuadrillas
                else None
            )
            delivery = AlertDelivery(
                alert_id=alert.id,
                channel=channel,
                recipients_count=recipients,
                at=now,
                source="SIMULADO",
            )
            session.add(delivery)
            deliveries.append(delivery)
        return deliveries


gateway: AlertGateway = SimulatedGateway()
