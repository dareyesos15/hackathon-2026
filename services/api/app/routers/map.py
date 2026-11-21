"""Capas del mapa: GET /map/manzanas (agregado) y GET /geo/barrios (mapa base offline)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.config import get_settings
from app.db import get_session
from app.domain import ReportStatus, Role
from app.models import Manzana, Report

router = APIRouter(tags=["mapa"])

TRIAGE_RANK_SQL = case(
    {"critico": 4, "alto": 3, "medio": 2, "bajo": 1}, value=Report.triage_level, else_=0
)
RANK_NAME = {4: "critico", 3: "alto", 2: "medio", 1: "bajo"}


@router.get("/map/manzanas")
async def manzanas_layer(
    role: Role = Depends(require_role(Role.operador_pmu, Role.publico)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """GeoJSON de manzanas con reportes vigentes. Para `publico`, k-anonimato (principio I)."""
    k = get_settings().k_anonymity
    stmt = (
        select(
            Manzana.id,
            Manzana.barrio,
            Manzana.source,
            func.ST_AsGeoJSON(Manzana.geom),
            func.count(Report.id),
            func.count(func.distinct(Report.incident_id)),
            func.max(TRIAGE_RANK_SQL),
        )
        .join(Report, Report.manzana_id == Manzana.id)
        .where(Report.status != ReportStatus.descartado)
        .group_by(Manzana.id)
    )
    rows = (await session.execute(stmt)).all()
    cutoff = datetime.now(UTC).isoformat()
    features = []
    for mid, barrio, source, geojson, reports, incidents, rank in rows:
        hide = role == Role.publico and reports < k
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "manzana_id": mid,
                    "barrio": barrio,
                    "report_count": None if hide else reports,
                    "incident_count": None if hide else incidents,
                    "max_triage_level": None if hide else RANK_NAME.get(rank),
                    "source": source,
                    "cutoff_at": cutoff,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features, "cutoff_at": cutoff}


@lru_cache
def _barrios() -> dict[str, Any]:
    path = get_settings().data_dir / "geo" / "barrios.geojson"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    data["names"] = sorted(f["properties"]["name"] for f in data["features"])
    return data


@router.get("/geo/barrios")
async def barrios_layer(
    _: Role = Depends(
        require_role(
            Role.operador_pmu, Role.publico, Role.ciudadano, Role.coe, Role.inspector, Role.agencia
        )
    ),
) -> dict[str, Any]:
    """Polígonos de barrios (SIMULADO) para el mapa base y lista de nombres para la PWA."""
    return _barrios()
