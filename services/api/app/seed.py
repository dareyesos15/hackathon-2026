"""Carga de la geografía (manzanas + gazetteer) al arrancar la API.

Idempotente y sincronizada con los archivos de data/geo/: si la base ya tiene exactamente la
misma geografía no hace nada; si los archivos cambiaron (p. ej. coordenadas corregidas con
OpenStreetMap), reemplaza lugares y manzanas. Los reportes e incidentes existentes conservan
sus coordenadas, pero pierden el enlace a la manzana vieja (se recomienda volver a reproducir
el escenario con --reset).
"""

import csv
import json
import logging

from geoalchemy2 import WKTElement
from shapely.geometry import shape
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import PlaceKind
from app.models import Incident, Manzana, Place, Report

log = logging.getLogger("dacora.seed")


def _coord(value: float | str) -> str:
    return f"{float(value):.5f}"


async def _sync_manzanas(session: AsyncSession, features: list[dict]) -> None:
    expected = {
        f["properties"]["id"]: (f["properties"]["barrio"], f["properties"]["comuna"])
        for f in features
    }
    rows = await session.execute(select(Manzana.id, Manzana.barrio, Manzana.comuna))
    current = {mid: (barrio, comuna) for mid, barrio, comuna in rows.all()}
    if current == expected:
        return
    if current:
        log.warning(
            "La geografía de manzanas cambió: se recarga (%s → %s)", len(current), len(expected)
        )
        await session.execute(
            update(Report).where(Report.manzana_id.is_not(None)).values(manzana_id=None)
        )
        await session.execute(
            update(Incident).where(Incident.manzana_id.is_not(None)).values(manzana_id=None)
        )
        await session.execute(delete(Manzana))
    for feature in features:
        props = feature["properties"]
        session.add(
            Manzana(
                id=props["id"],
                geom=WKTElement(shape(feature["geometry"]).wkt, srid=4326),
                barrio=props["barrio"],
                comuna=props["comuna"],
                seismic_zone=props["seismic_zone"],
                population=props["population"],
                buildings_pre_1984_pct=props["buildings_pre_1984_pct"],
                source=props.get("source", "SIMULADO"),
            )
        )
    log.info("Manzanas cargadas: %s", len(features))


async def _sync_places(session: AsyncSession, rows: list[dict[str, str]]) -> None:
    expected = {(r["name"], _coord(r["lat"]), _coord(r["lon"]), r["barrio"]) for r in rows}
    result = await session.execute(
        select(Place.name, func.ST_Y(Place.geom), func.ST_X(Place.geom), Place.barrio)
    )
    current = {(n, _coord(lat), _coord(lon), b) for n, lat, lon, b in result.all()}
    if current == expected:
        return
    if current:
        log.warning("El gazetteer cambió: se recargan %s lugares", len(rows))
        await session.execute(delete(Place))
    for row in rows:
        session.add(
            Place(
                name=row["name"],
                kind=PlaceKind(row["kind"]),
                aliases=[a for a in row["aliases"].split("|") if a],
                geom=WKTElement(f"POINT({row['lon']} {row['lat']})", srid=4326),
                barrio=row["barrio"],
                source=row.get("source", "SIMULADO"),
            )
        )
    log.info("Lugares del gazetteer cargados: %s", len(rows))


async def seed_geography(session: AsyncSession) -> None:
    geo_dir = get_settings().data_dir / "geo"
    manzanas = json.loads((geo_dir / "manzanas.geojson").read_text(encoding="utf-8"))
    with (geo_dir / "gazetteer.csv").open(encoding="utf-8") as fh:
        places = list(csv.DictReader(fh))

    await _sync_manzanas(session, manzanas["features"])
    await _sync_places(session, places)
    await session.commit()
