"""Fuente de lecturas del sensor de zonas inseguras (patente NC2025/0015763). Interfaz
`ZoneSensorFeed` (principio VI): hoy SIMULADA; un dispositivo real enviaría sus lecturas a
`POST /api/v1/sensors/zones/{id}/readings` con el mismo formato.

`SimulatedZoneSensorFeed` corre como tarea asyncio en el `lifespan` de la API y genera, cada
`tick_s` segundos, una lectura sintética en un sensor armado al azar:

- rescatista con credencial RFID registrada dentro del cono → acceso autorizado (sin alarma);
- civil sin tarjeta, o con tarjeta desconocida, dentro del cono → intrusión;
- objetivo fuera del cono → sin evento (solo latido);
- descarga de batería y, rara vez, apertura de la carcasa.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain import ZoneSensorStatus
from app.models import RfidBadge, ZoneSensor
from app.zone_schemas import ZoneReadingIn

log = logging.getLogger("dacora.zone_sensor")

Processor = Callable[[AsyncSession, ZoneSensor, ZoneReadingIn, datetime], Awaitable[object]]


class ZoneSensorFeed(Protocol):
    async def run(self) -> None: ...


def synthetic_reading(rng: random.Random, sensor: ZoneSensor, badges: list[str]) -> ZoneReadingIn:
    """Lectura sintética plausible para un sensor (ver docstring del módulo)."""
    battery = max(0, sensor.battery_pct - rng.choice((0, 0, 1, 1, 2)))
    if battery < 10:
        battery = 100  # cambio de batería por la cuadrilla
    inside_dist = round(rng.uniform(1.0, sensor.range_m * 0.95), 1)
    inside_bearing = round(rng.uniform(-sensor.half_angle_deg, sensor.half_angle_deg) * 0.9, 1)
    r = rng.random()
    if r < 0.38 and badges:  # rescatista autorizado
        return ZoneReadingIn(
            ultrasonic_m=inside_dist,
            infrared=True,
            bearing_deg=inside_bearing,
            rfid_tag=rng.choice(badges),
            battery_pct=battery,
        )
    if r < 0.60:  # civil sin tarjeta
        both = rng.random() < 0.7
        return ZoneReadingIn(
            ultrasonic_m=inside_dist if both or rng.random() < 0.5 else None,
            infrared=True if both else rng.random() < 0.5,
            bearing_deg=inside_bearing,
            battery_pct=battery,
        )
    if r < 0.67:  # tarjeta no registrada
        return ZoneReadingIn(
            ultrasonic_m=inside_dist,
            infrared=True,
            bearing_deg=inside_bearing,
            rfid_tag=f"VIS-{rng.randint(1000, 9999)}",
            battery_pct=battery,
        )
    if r < 0.985:  # objetivo fuera del cono: sin evento
        return ZoneReadingIn(
            ultrasonic_m=round(sensor.range_m * rng.uniform(1.1, 2.5), 1),
            infrared=False,
            bearing_deg=round(sensor.half_angle_deg + rng.uniform(5, 60), 1),
            battery_pct=battery,
        )
    return ZoneReadingIn(tamper=True, battery_pct=battery)


class SimulatedZoneSensorFeed:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        process: Processor,
        *,
        tick_s: float,
        seed: int | None = None,
    ) -> None:
        self._sessions = session_factory
        self._process = process
        self._tick_s = tick_s
        self._rng = random.Random(seed)

    async def tick(self, now: datetime) -> bool:
        async with self._sessions() as session:
            sensors = list(
                (
                    await session.execute(
                        select(ZoneSensor).where(ZoneSensor.status == ZoneSensorStatus.armado)
                    )
                ).scalars()
            )
            if not sensors:
                return False
            badges = list((await session.execute(select(RfidBadge.tag))).scalars())
            sensor = self._rng.choice(sensors)
            await self._process(session, sensor, synthetic_reading(self._rng, sensor, badges), now)
            return True

    async def run(self) -> None:
        log.info("Sensor de zonas inseguras SIMULADO activo (cada %ss)", self._tick_s)
        while True:
            try:
                await self.tick(datetime.now(UTC))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - el feed no debe tumbar la API
                log.exception("Fallo en el sensor de zonas simulado")
            await asyncio.sleep(self._tick_s * self._rng.uniform(0.6, 1.4))
