"""Lector de control vehicular tipo RFID (patente 15111163). Interfaz `TrackFeed` (principio VI).

`SimulatedRfidFeed` (research R4) corre como tarea asyncio en el `lifespan` de la API: hace
avanzar los despachos `en_camino` en línea recta base → incidente, con puntos de control en 1/3 y
2/3 del trayecto y la llegada, comprimiendo el tiempo `track_speedup` veces. Usa la misma
función de dominio que el endpoint manual, así que el resultado es el de un lector real.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.dispatch import (
    TrackResult,
    incident_point,
    interpolate,
    planned_checkpoints,
    record_track,
)
from app.domain import DispatchStatus, Role, TrackKind, TrackOrigin
from app.models import Dispatch, Incident, Resource, ResourceTrack

log = logging.getLogger("dacora.tracks")

Publisher = Callable[[AsyncSession, TrackResult], Awaitable[None]]


class TrackFeed(Protocol):
    async def run(self) -> None: ...


class SimulatedRfidFeed:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        publish: Publisher,
        *,
        tick_s: float,
        speedup: float,
    ) -> None:
        self._sessions = session_factory
        self._publish = publish
        self._tick_s = tick_s
        self._speedup = speedup

    async def tick(self, now: datetime) -> int:
        """Registra los puntos de paso vencidos. Devuelve cuántos registró."""
        recorded = 0
        async with self._sessions() as session:
            dispatches = list(
                (
                    await session.execute(
                        select(Dispatch).where(Dispatch.status == DispatchStatus.en_camino)
                    )
                ).scalars()
            )
            for dispatch in dispatches:
                recorded += await self._advance(session, dispatch, now)
        return recorded

    async def _advance(self, session: AsyncSession, dispatch: Dispatch, now: datetime) -> int:
        rows = (
            await session.execute(
                select(
                    ResourceTrack.kind,
                    func.ST_Y(ResourceTrack.geom),
                    func.ST_X(ResourceTrack.geom),
                )
                .where(ResourceTrack.dispatch_id == dispatch.id)
                .order_by(ResourceTrack.at)
            )
        ).all()
        start = next(((lat, lon) for kind, lat, lon in rows if kind == TrackKind.salida), None)
        incident = await session.get(Incident, dispatch.incident_id)
        target = await incident_point(session, incident) if incident else None
        if start is None or target is None:
            return 0
        done = sum(1 for kind, _, _ in rows if kind in (TrackKind.control, TrackKind.llegada))
        recorded = 0
        plan = planned_checkpoints(dispatch.created_at, dispatch.eta_at, self._speedup)
        for index, (kind, fraction, at) in enumerate(plan):
            if index < done:
                continue
            if at > now:
                break
            resource = await session.get(Resource, dispatch.resource_id)
            assert resource is not None
            lat, lon = interpolate(start, target, fraction)
            result = await record_track(
                session,
                resource,
                kind=TrackKind(kind),
                origin=TrackOrigin.rfid_simulado,
                lat=lat,
                lon=lon,
                at=at,
                actor=Role.sistema,
            )
            await self._publish(session, result)
            recorded += 1
        return recorded

    async def run(self) -> None:
        log.info("Avance SIMULADO de recursos activo (cada %ss, %s×)", self._tick_s, self._speedup)
        while True:
            try:
                await self.tick(datetime.now(UTC))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - el feed no debe tumbar la API
                log.exception("Fallo en el avance simulado de recursos")
            await asyncio.sleep(self._tick_s)
