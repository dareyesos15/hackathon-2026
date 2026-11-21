"""Carga idempotente de la geografía SIMULADA (manzanas + gazetteer) al arrancar la API."""

import csv
import json
import logging

from geoalchemy2 import WKTElement
from shapely.geometry import shape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import PlaceKind
from app.models import Manzana, Place

log = logging.getLogger("dacora.seed")


async def seed_geography(session: AsyncSession) -> None:
    geo_dir = get_settings().data_dir / "geo"

    if not await session.scalar(select(func.count()).select_from(Manzana)):
        data = json.loads((geo_dir / "manzanas.geojson").read_text(encoding="utf-8"))
        for feature in data["features"]:
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
        log.info("Manzanas cargadas: %s", len(data["features"]))

    if not await session.scalar(select(func.count()).select_from(Place)):
        with (geo_dir / "gazetteer.csv").open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
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

    await session.commit()
