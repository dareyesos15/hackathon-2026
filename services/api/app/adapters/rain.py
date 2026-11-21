"""Fuente de lluvia para la predicción de cascada (specs/002 US3, research R11).

Dos fuentes, elegidas en caliente por el administrador (`PUT /sensors/rain/source`):

- `simulado` (por defecto): la última lectura SIMULADA (`POST /sensors/rain`, curva del replay o
  deslizador del tablero), un único valor para toda la ciudad.
- `cdiac`: precipitación **real en vivo** de las estaciones hidrometeorológicas urbanas del
  CDIAC/SIMAC (UNAL Manizales), consultada cada `cdiac_poll_s` desde la API pública que usa el
  geoportal SIMAC (`etl-cdiac/api/apiGeo`). Cada estación se guarda como una lectura en
  `rain_readings` (`source = "CDIAC/SIMAC"`) y la cascada la interpola por manzana (IDW).

Respaldo (offline-first, principio VII): si CDIAC no responde o sus datos tienen más de
`cdiac_max_age_min`, la cascada vuelve sola a la lluvia SIMULADA y lo dice en el desglose. Solo
la API habla con CDIAC; el frontend nunca.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import RainReading

log = logging.getLogger("dacora.rain")

CDIAC_SOURCE = "CDIAC/SIMAC"
CDIAC_PREFIX = "CDIAC-"
ATTRIBUTION = "Precipitación: CDIAC / SIMAC — Universidad Nacional de Colombia, sede Manizales"
COLOMBIA_TZ = timezone(timedelta(hours=-5))  # sin horario de verano
WINDOW = timedelta(hours=3)


class RainSource(StrEnum):
    simulado = "simulado"
    cdiac = "cdiac"


@dataclass(frozen=True)
class Station:
    id: int
    name: str
    lat: float
    lon: float

    @property
    def code(self) -> str:
        return f"{CDIAC_PREFIX}{self.id}"


@dataclass(frozen=True)
class StationRain:
    station: Station
    mm_3h: float
    last_data_at: datetime


class CdiacRainClient:
    """Cliente mínimo de la API pública del geoportal SIMAC (solo POST, sin autenticación)."""

    def __init__(
        self,
        base_url: str,
        catalog_file: Path,
        *,
        timeout_s: float = 10.0,
        concurrency: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.catalog_file = catalog_file
        self.timeout_s = timeout_s
        self.concurrency = concurrency
        self._catalog: dict[str, Station] | None = None

    def catalog(self) -> dict[str, Station]:
        """Estaciones urbanas (copia local del catálogo público; funciona sin red)."""
        if self._catalog is None:
            try:
                raw = json.loads(self.catalog_file.read_text(encoding="utf-8"))
                stations = [
                    Station(int(s["id"]), str(s["name"]), float(s["lat"]), float(s["lon"]))
                    for s in raw["stations"]
                ]
            except (OSError, ValueError, KeyError) as exc:
                log.warning("Catálogo de estaciones CDIAC no disponible: %s", exc)
                stations = []
            self._catalog = {s.code: s for s in stations}
        return self._catalog

    async def fetch(self, now: datetime, max_age: timedelta) -> list[StationRain]:
        """Lluvia de las últimas 3 h por estación. Omite estaciones sin dato reciente."""
        stations = list(self.catalog().values())
        if not stations:
            raise RuntimeError("sin catálogo de estaciones CDIAC")
        sem = asyncio.Semaphore(self.concurrency)
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:

            async def one(st: Station) -> StationRain | None:
                async with sem:
                    try:
                        resp = await client.post(f"{self.base_url}/getLastDayDataByStation/{st.id}")
                        resp.raise_for_status()
                        rows = resp.json()
                    except (httpx.HTTPError, ValueError):
                        return None
                return _station_rain(st, rows, now, max_age)

            results = await asyncio.gather(*(one(s) for s in stations))
        ok = [r for r in results if r is not None]
        if not ok:
            raise RuntimeError("CDIAC no devolvió precipitación reciente en ninguna estación")
        return ok


def _parse_ts(row: dict[str, Any]) -> datetime | None:
    try:
        local = datetime.fromisoformat(f"{row['date']}T{row['time']}")
    except (KeyError, TypeError, ValueError):
        return None
    return local.replace(tzinfo=COLOMBIA_TZ).astimezone(UTC)


def _station_rain(st: Station, rows: Any, now: datetime, max_age: timedelta) -> StationRain | None:
    if not isinstance(rows, list):
        return None
    points: list[tuple[datetime, float]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("precipitation") is None:
            continue
        ts = _parse_ts(row)
        if ts is None:
            continue
        try:
            points.append((ts, max(0.0, float(row["precipitation"]))))
        except (TypeError, ValueError):
            continue
    if not points:
        return None
    last = max(ts for ts, _ in points)
    if now - last > max_age:
        return None
    total = sum(mm for ts, mm in points if ts > last - WINDOW)
    return StationRain(st, round(min(total, 300.0), 1), last)


@dataclass
class RainFeed:
    """Sondeo periódico de CDIAC mientras la fuente activa sea `cdiac`."""

    client: CdiacRainClient
    poll_s: float = 300.0
    max_age: timedelta = timedelta(minutes=60)
    source: RainSource = RainSource.simulado
    last_attempt_at: datetime | None = None
    last_ok_at: datetime | None = None
    last_error: str | None = None
    readings: list[StationRain] = field(default_factory=list)
    _wake: asyncio.Event = field(default_factory=asyncio.Event)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_fresh(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return (
            self.source == RainSource.cdiac
            and self.last_ok_at is not None
            and now - self.last_ok_at <= self.max_age
            and bool(self.readings)
        )

    def forget(self) -> None:
        """Tras reiniciar la demo (se borraron las lecturas): vuelve a consultar ya."""
        self.readings = []
        self.last_ok_at = None
        self._wake.set()

    def set_source(self, source: RainSource) -> None:
        self.source = source
        self._wake.set()

    async def refresh(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        on_change: Callable[[], None],
    ) -> None:
        async with self._lock:
            now = datetime.now(UTC)
            self.last_attempt_at = now
            try:
                readings = await self.client.fetch(now, self.max_age)
            except Exception as exc:  # noqa: BLE001 - el respaldo es la lluvia SIMULADA
                self.last_error = str(exc) or exc.__class__.__name__
                log.warning("Lluvia CDIAC no disponible (se usa respaldo SIMULADO): %s", exc)
                on_change()
                return
            async with session_factory() as session:
                session.add_all(
                    RainReading(
                        station_code=r.station.code,
                        mm_3h=r.mm_3h,
                        at=now,
                        source=CDIAC_SOURCE,
                    )
                    for r in readings
                )
                await session.commit()
            self.readings = readings
            self.last_ok_at = now
            self.last_error = None
            log.info(
                "Lluvia CDIAC: %d estaciones, máx. %.1f mm/3 h",
                len(readings),
                max(r.mm_3h for r in readings),
            )
            on_change()

    async def run(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        on_change: Callable[[], None],
    ) -> None:
        while True:
            if self.source == RainSource.cdiac:
                await self.refresh(session_factory, on_change)
            self._wake.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=self.poll_s)


def build_feed() -> RainFeed:
    from app.config import get_settings

    s = get_settings()
    client = CdiacRainClient(
        s.cdiac_base_url,
        s.data_dir / "geo" / "cdiac_rain_stations.json",
        timeout_s=s.cdiac_timeout_s,
    )
    return RainFeed(
        client=client,
        poll_s=s.cdiac_poll_s,
        max_age=timedelta(minutes=s.cdiac_max_age_min),
        source=RainSource(s.rain_source),
    )


rain_feed: RainFeed = build_feed()
