"""Predicción de efectos en cascada por manzana (specs/002 US3, research R11).

Riesgo de deslizamiento o colapso secundario explicable con cuatro factores: pendiente
(SIMULADA), lluvia acumulada en 3 h (feed SIMULADO), intensidad sísmica (`HazardProvider`,
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
        "reportes_cercanos": part(
            reports,
            cfg.weight_reports,
            f"{nearby_reports} reportes a ≤ {cfg.reports_radius_m:.0f} m en "
            f"{cfg.reports_window_hours:.0f} h",
        ),
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
    return (
        await session.execute(select(RainReading).order_by(RainReading.at.desc()).limit(1))
    ).scalar_one_or_none()


async def compute(
    session: AsyncSession,
    cfg: CascadeSettings,
    terrain: TerrainProvider,
    hazard: HazardProvider,
) -> dict[str, Any]:
    """GeoJSON de manzanas con nivel y desglose. Caché en memoria (invalidación + 30 s)."""
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_S:
        return _cache[1]

    manzanas = await _load_manzanas(session)
    rain = await latest_rain(session)
    rain_mm = float(rain.mm_3h) if rain else None
    rain_detail = (
        f"{rain_mm:.0f} mm en 3 h ({rain.station_code}, SIMULADO)"
        if rain
        else "sin dato de lluvia (0 mm)"
    )
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
        "rain_mm_3h": rain_mm,
        "model_version": MODEL_VERSION,
    }
    _cache = (time.monotonic(), result)
    return result
