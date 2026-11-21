"""Predicción de efectos en cascada por manzana (specs/002 US3, research R11).

Riesgo de deslizamiento o colapso secundario explicable con cuatro factores: pendiente
(SIMULADA), lluvia acumulada en 3 h (SIMULADA o real del CDIAC/SIMAC interpolada por manzana,
ver `app.adapters.rain`), intensidad sísmica (`HazardProvider`,
neutra sin sensores) y reportes recientes de daño, colapso o deslizamiento cercanos. Las
"últimas horas" se miden con el reloj del escenario (`max(reports.occurred_at)`).
Es solo una sugerencia: nunca despacha ni emite alertas (FR-031).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.hazard import HazardProvider
from app.adapters.rain import CDIAC_SOURCE, RainFeed, RainSource
from app.adapters.terrain import TerrainProvider
from app.config import CascadeSettings
from app.core.geo import haversine_m
from app.domain import CascadeLevel, Category, ReportStatus
from app.models import Manzana, RainReading, Report

MODEL_VERSION = "cascade-v1"
RELEVANT = (Category.dano_estructural, Category.colapso_estructura, Category.deslizamiento)
CACHE_TTL_S = 30.0


@dataclass(frozen=True)
class ManzanaInfo:
    id: str
    barrio: str
    seismic_zone: str
    lat: float
    lon: float
    geometry: dict[str, Any]


_manzanas: list[ManzanaInfo] | None = None
_cache: tuple[float, dict[str, Any]] | None = None


def invalidate() -> None:
    global _cache
    _cache = None


def level_for(score: float, cfg: CascadeSettings) -> CascadeLevel:
    if score >= cfg.cut_muy_alto:
        return CascadeLevel.muy_alto
    if score >= cfg.cut_alto:
        return CascadeLevel.alto
    if score >= cfg.cut_medio:
        return CascadeLevel.medio
    return CascadeLevel.bajo


def score_manzana(
    *,
    slope_deg: float,
    zone_label: str,
    rain_mm: float | None,
    rain_detail: str,
    seismic_value: float,
    seismic_detail: str,
    nearby_reports: int,
    cfg: CascadeSettings,
) -> tuple[float, dict[str, dict[str, Any]]]:
    def part(points: float, weight: float, detail: str) -> dict[str, Any]:
        return {"puntos": round(points, 1), "max": weight, "detalle": detail}

    slope = cfg.weight_slope * min(1.0, slope_deg / cfg.slope_saturation_deg)
    rain = cfg.weight_rain * min(1.0, (rain_mm or 0.0) / cfg.rain_saturation_mm)
    seismic = cfg.weight_seismic * max(0.0, min(1.0, seismic_value))
    reports = cfg.weight_reports * min(1.0, nearby_reports / cfg.reports_saturation)
    breakdown = {
        "pendiente": part(slope, cfg.weight_slope, f"{slope_deg:.0f}° ({zone_label}, SIMULADO)"),
        "lluvia": part(rain, cfg.weight_rain, rain_detail),
        "sismo": part(seismic, cfg.weight_seismic, seismic_detail),
        "reportes_cercanos": {
            **part(
                reports,
                cfg.weight_reports,
                f"{nearby_reports} reportes a ≤ {cfg.reports_radius_m:.0f} m en "
                f"{cfg.reports_window_hours:.0f} h",
            ),
            "n": nearby_reports,
        },
    }
    return round(slope + rain + seismic + reports, 1), breakdown


async def _load_manzanas(session: AsyncSession) -> list[ManzanaInfo]:
    global _manzanas
    if _manzanas is None:
        centroid = func.ST_Centroid(Manzana.geom)
        rows = (
            await session.execute(
                select(
                    Manzana.id,
                    Manzana.barrio,
                    Manzana.seismic_zone,
                    func.ST_Y(centroid),
                    func.ST_X(centroid),
                    func.ST_AsGeoJSON(Manzana.geom, 6),
                )
            )
        ).all()
        _manzanas = [
            ManzanaInfo(mid, barrio, zone, float(lat), float(lon), json.loads(geo))
            for mid, barrio, zone, lat, lon, geo in rows
        ]
    return _manzanas


async def latest_rain(session: AsyncSession) -> RainReading | None:
    """Última lectura SIMULADA (replay o deslizador). Las de CDIAC van por `rain_field`."""
    return (
        await session.execute(
            select(RainReading)
            .where(RainReading.source != CDIAC_SOURCE)
            .order_by(RainReading.at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class RainStation:
    name: str
    lat: float
    lon: float
    mm: float


@dataclass(frozen=True)
class RainField:
    """Lluvia en 3 h a usar por manzana: un valor único (SIMULADO) o estaciones reales (IDW)."""

    source: str  # "simulado" | "cdiac" | "cdiac_respaldo"
    summary_mm: float | None
    summary_detail: str
    stations: tuple[RainStation, ...] = ()

    def at(self, lat: float, lon: float) -> tuple[float | None, str]:
        if not self.stations:
            return self.summary_mm, self.summary_detail
        num = den = 0.0
        nearest = min(self.stations, key=lambda s: haversine_m(lat, lon, s.lat, s.lon))
        for st in self.stations:
            d = max(haversine_m(lat, lon, st.lat, st.lon), 50.0)
            w = 1.0 / (d * d)
            num += w * st.mm
            den += w
        mm = num / den
        dist_km = haversine_m(lat, lon, nearest.lat, nearest.lon) / 1000
        return mm, (
            f"{mm:.1f} mm en 3 h (CDIAC/SIMAC, IDW de {len(self.stations)} estaciones; "
            f"más cercana: {nearest.name}, {nearest.mm:.1f} mm a {dist_km:.1f} km)"
        )


async def rain_field(session: AsyncSession, feed: RainFeed) -> RainField:
    if feed.source == RainSource.cdiac:
        since = datetime.now(UTC) - feed.max_age
        rows = (
            await session.execute(
                select(RainReading.station_code, RainReading.mm_3h)
                .where(RainReading.source == CDIAC_SOURCE, RainReading.at >= since)
                .order_by(RainReading.at.desc())
            )
        ).all()
        catalog = feed.client.catalog()
        latest: dict[str, float] = {}
        for code, mm in rows:
            latest.setdefault(code, float(mm))
        stations = tuple(
            RainStation(catalog[code].name, catalog[code].lat, catalog[code].lon, mm)
            for code, mm in latest.items()
            if code in catalog
        )
        if stations:
            top = max(stations, key=lambda s: s.mm)
            return RainField(
                source="cdiac",
                summary_mm=top.mm,
                summary_detail=f"máx. {top.mm:.1f} mm en 3 h ({top.name}, CDIAC/SIMAC)",
                stations=stations,
            )
    reading = await latest_rain(session)
    sim_mm = float(reading.mm_3h) if reading else None
    detail = (
        f"{sim_mm:.0f} mm en 3 h ({reading.station_code}, SIMULADO)"
        if reading
        else "sin dato de lluvia (0 mm)"
    )
    if feed.source == RainSource.cdiac:
        return RainField("cdiac_respaldo", sim_mm, f"respaldo: CDIAC sin datos recientes; {detail}")
    return RainField("simulado", sim_mm, detail)


async def compute(
    session: AsyncSession,
    cfg: CascadeSettings,
    terrain: TerrainProvider,
    hazard: HazardProvider,
    feed: RainFeed,
) -> dict[str, Any]:
    """GeoJSON de manzanas con nivel y desglose. Caché en memoria (invalidación + 30 s)."""
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_S:
        return _cache[1]

    manzanas = await _load_manzanas(session)
    rain = await rain_field(session, feed)
    clock = await session.scalar(select(func.max(Report.occurred_at)))
    points: list[tuple[float, float]] = []
    if clock is not None:
        since = clock - timedelta(hours=cfg.reports_window_hours)
        rows = (
            await session.execute(
                select(func.ST_Y(Report.geom), func.ST_X(Report.geom)).where(
                    Report.category.in_(list(RELEVANT)),
                    Report.status != ReportStatus.descartado,
                    Report.occurred_at >= since,
                    Report.geom.is_not(None),
                )
            )
        ).all()
        points = [(float(lat), float(lon)) for lat, lon in rows]

    features = []
    for m in manzanas:
        nearby = sum(
            1 for lat, lon in points if haversine_m(m.lat, m.lon, lat, lon) <= cfg.reports_radius_m
        )
        consistency = hazard.consistency(m.id, Category.deslizamiento.value)
        rain_mm, rain_detail = rain.at(m.lat, m.lon)
        score, breakdown = score_manzana(
            slope_deg=terrain.slope_deg(m.id, m.seismic_zone),
            zone_label="ladera" if "ladera" in m.seismic_zone.lower() else "meseta",
            rain_mm=rain_mm,
            rain_detail=rain_detail,
            seismic_value=consistency.value,
            seismic_detail=consistency.detail,
            nearby_reports=nearby,
            cfg=cfg,
        )
        features.append(
            {
                "type": "Feature",
                "geometry": m.geometry,
                "properties": {
                    "manzana_id": m.id,
                    "barrio": m.barrio,
                    "level": level_for(score, cfg).value,
                    "score": score,
                    "slope_deg": terrain.slope_deg(m.id, m.seismic_zone),
                    "breakdown": breakdown,
                    "model_version": MODEL_VERSION,
                    "source": "SIMULADO",
                },
            }
        )
    result = {
        "type": "FeatureCollection",
        "features": features,
        "cutoff_at": datetime.now(UTC).isoformat(),
        "scenario_clock": clock.isoformat() if clock else None,
        "rain_mm_3h": rain.summary_mm,
        "rain_source": rain.source,
        "rain_detail": rain.summary_detail,
        "model_version": MODEL_VERSION,
    }
    _cache = (time.monotonic(), result)
    return result
