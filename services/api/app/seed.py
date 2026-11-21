"""Carga de datos SIMULADOS de referencia al arrancar la API.

Geografía (manzanas + gazetteer): idempotente y sincronizada con los archivos de data/geo/: si la
base ya tiene exactamente la misma geografía no hace nada; si los archivos cambiaron (p. ej.
coordenadas corregidas con OpenStreetMap), reemplaza lugares y manzanas. Los reportes e
incidentes existentes conservan sus coordenadas, pero pierden el enlace a la manzana vieja (se
recomienda volver a reproducir el escenario con --reset).

Catálogo de agencias y recursos del despacho (specs/002): se carga una vez.
"""

import csv
import json
import logging
from typing import Any, cast

from geoalchemy2 import WKTElement
from shapely.geometry import shape
from sqlalchemy import CursorResult, TextClause, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain import EmreFunction, PlaceKind, ResourceStatus, ResourceType
from app.models import (
    Agency,
    Alert,
    Incident,
    Manzana,
    Place,
    Report,
    Resource,
    RfidBadge,
    Shelter,
    ZoneSensor,
)

log = logging.getLogger("dacora.seed")


def _coord(value: float | str) -> str:
    return f"{float(value):.5f}"


async def _sync_manzanas(session: AsyncSession, features: list[dict[str, Any]]) -> None:
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
        # Alertas creadas desde la capa de cascada (specs/002) apuntan a una manzana.
        await session.execute(
            update(Alert).where(Alert.origin_manzana_id.is_not(None)).values(origin_manzana_id=None)
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


# Reportes e incidentes con punto (GPS o barrio) pero sin manzana o barrio: se completan con la
# manzana que contiene el punto. Cubre los datos previos a la corrección de GPS y las manzanas
# desvinculadas al recargar la geografía.
_BACKFILL_REPORTS = text(
    """
    UPDATE reports r
       SET manzana_id = COALESCE(r.manzana_id, m.id),
           barrio = CASE WHEN r.geo_precision = 'gps' THEN m.barrio
                         ELSE COALESCE(r.barrio, m.barrio) END
      FROM manzanas m
     WHERE r.geom IS NOT NULL
       AND ST_Contains(m.geom, r.geom)
       AND (r.manzana_id IS NULL OR r.barrio IS NULL)
    """
)
_BACKFILL_INCIDENTS = text(
    """
    UPDATE incidents i
       SET manzana_id = COALESCE(i.manzana_id, m.id),
           barrio = COALESCE(i.barrio, m.barrio)
      FROM manzanas m
     WHERE i.centroid IS NOT NULL
       AND ST_Contains(m.geom, i.centroid)
       AND (i.manzana_id IS NULL OR i.barrio IS NULL)
    """
)


# Puntos fuera de la grilla de manzanas: barrio más cercano a menos de 1,5 km.
_BACKFILL_NEAREST = text(
    """
    UPDATE reports r
       SET barrio = (
           SELECT p.barrio FROM places p
            WHERE p.kind = 'barrio'
              AND ST_DWithin(p.geom::geography, r.geom::geography, 1500)
            ORDER BY ST_Distance(p.geom::geography, r.geom::geography)
            LIMIT 1)
     WHERE r.geom IS NOT NULL AND r.barrio IS NULL
       AND EXISTS (
           SELECT 1 FROM places p
            WHERE p.kind = 'barrio'
              AND ST_DWithin(p.geom::geography, r.geom::geography, 1500))
    """
)
_BACKFILL_INCIDENT_FROM_REPORTS = text(
    """
    UPDATE incidents i
       SET barrio = (
           SELECT r.barrio FROM reports r
            WHERE r.incident_id = i.id AND r.barrio IS NOT NULL
            ORDER BY (r.geo_precision = 'gps') DESC
            LIMIT 1)
     WHERE i.barrio IS NULL
       AND EXISTS (
           SELECT 1 FROM reports r WHERE r.incident_id = i.id AND r.barrio IS NOT NULL)
    """
)


async def _updated(session: AsyncSession, stmt: TextClause) -> int:
    """Filas afectadas por un UPDATE (CursorResult.rowcount)."""
    result = cast(CursorResult[Any], await session.execute(stmt))
    return result.rowcount or 0


async def _backfill_locations(session: AsyncSession) -> None:
    reports = await _updated(session, _BACKFILL_REPORTS)
    reports += await _updated(session, _BACKFILL_NEAREST)
    incidents = await _updated(session, _BACKFILL_INCIDENTS)
    incidents += await _updated(session, _BACKFILL_INCIDENT_FROM_REPORTS)
    if reports or incidents:
        log.info("Barrio/manzana completados: %s reportes, %s incidentes", reports, incidents)


async def seed_geography(session: AsyncSession) -> None:
    geo_dir = get_settings().data_dir / "geo"
    manzanas = json.loads((geo_dir / "manzanas.geojson").read_text(encoding="utf-8"))
    with (geo_dir / "gazetteer.csv").open(encoding="utf-8") as fh:
        places = list(csv.DictReader(fh))

    await _sync_manzanas(session, manzanas["features"])
    await _sync_places(session, places)
    await session.flush()
    await _backfill_locations(session)
    await session.commit()


async def seed_catalog(session: AsyncSession) -> None:
    """Agencias y recursos de `data/seed/resources.json` (research R1). Solo si no existen."""
    if await session.scalar(select(func.count()).select_from(Agency)):
        return
    path = get_settings().data_dir / "seed" / "resources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    source = data.get("source", "SIMULADO")
    agencies: dict[str, Agency] = {}
    for row in data["agencies"]:
        agency = Agency(
            code=row["code"],
            name=row["name"],
            emre_function=EmreFunction(row["emre_function"]),
            source=source,
        )
        session.add(agency)
        agencies[row["code"]] = agency
    await session.flush()
    for row in data["resources"]:
        point = WKTElement(f"POINT({row['lon']} {row['lat']})", srid=4326)
        session.add(
            Resource(
                code=row["code"],
                agency_id=agencies[row["agency"]].id,
                type=ResourceType(row["type"]),
                label=row["label"],
                base_geom=point,
                last_geom=point,
                status=ResourceStatus.disponible,
                source=source,
            )
        )
    await session.commit()
    log.info(
        "Catálogo de despacho cargado: %s agencias, %s recursos",
        len(agencies),
        len(data["resources"]),
    )


SHELTERS = [
    ("ALB-01", "Coliseo Mayor", "Palogrande", 5.05804, -75.48845, 400),
    ("ALB-02", "Estadio Palogrande · gradería sur", "Palogrande", 5.05703, -75.49009, 250),
    ("ALB-03", "Institución educativa · sede Milán", "Milán", 5.04590, -75.47986, 120),
    ("ALB-04", "Salón comunal La Enea", "La Enea", 5.03182, -75.46306, 80),
    ("ALB-05", "Polideportivo Chipre", "Chipre", 5.07584, -75.52544, 150),
]


async def seed_shelters(session: AsyncSession) -> None:
    """Albergues temporales SIMULADOS (specs/003 US4). Solo si no existen."""
    if await session.scalar(select(func.count()).select_from(Shelter)):
        return
    for code, name, barrio, lat, lon, capacity in SHELTERS:
        session.add(
            Shelter(
                code=code,
                name=name,
                barrio=barrio,
                capacity=capacity,
                people=0,
                pets=0,
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                source="SIMULADO",
            )
        )
    await session.commit()
    log.info("Albergues SIMULADOS cargados: %s", len(SHELTERS))


ZONE_SENSORS = [
    ("ZI-001", "Edificio acordonado · Catedral", 5.06738, -75.51732, 90),
    ("ZI-002", "Edificio acordonado · carrera 23", 5.06716, -75.51535, 180),
    ("ZI-003", "Torre residencial · Av. Santander", 5.06216, -75.49415, 45),
    ("ZI-004", "Bodega con daño mayor · Av. Paralela", 5.06062, -75.49559, 270),
    ("ZI-005", "Casa en bahareque · San José", 5.07203, -75.51488, 135),
    ("ZI-006", "Edificio con colapso parcial · Milán", 5.04590, -75.47986, 315),
]

RFID_BADGES = [
    *((f"BOM-{n:04d}", "BOMBEROS", "Bombero") for n in range(101, 109)),
    *((f"DC-{n:04d}", "DEFENSA_CIVIL", "Socorrista Defensa Civil") for n in range(201, 206)),
    *((f"CR-{n:04d}", "CRUZ_ROJA", "Socorrista Cruz Roja") for n in range(301, 305)),
    *((f"INF-{n:04d}", "SEC_INFRAESTRUCTURA", "Ingeniero evaluador") for n in range(401, 405)),
]


async def seed_zone_sensors(session: AsyncSession) -> None:
    """Sensores de zonas inseguras y credenciales RFID SIMULADOS (specs/004). Solo si no existen."""
    if await session.scalar(select(func.count()).select_from(ZoneSensor)):
        return
    source = "SIMULADO · patente NC2025/0015763"
    for code, label, lat, lon, heading in ZONE_SENSORS:
        session.add(
            ZoneSensor(
                code=code,
                label=label,
                geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                heading_deg=heading,
                range_m=12,
                half_angle_deg=30,
                battery_pct=100,
                source=source,
            )
        )
    for tag, agency, role_label in RFID_BADGES:
        session.add(RfidBadge(tag=tag, agency_code=agency, role_label=role_label, source=source))
    await session.commit()
    log.info(
        "Sensores de zonas inseguras SIMULADOS: %s · credenciales RFID: %s",
        len(ZONE_SENSORS),
        len(RFID_BADGES),
    )
