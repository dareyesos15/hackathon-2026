"""Ubicación de reportes sin GPS con el gazetteer local de Manizales (FR-012).

Funciones puras: la carga desde la base y el punto→manzana (PostGIS) viven en el pipeline.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.core.text import normalize
from app.domain import GeoPrecision, PlaceKind

# Rectángulo de Manizales (data-model.md, reglas de validación).
LAT_MIN, LAT_MAX = 4.95, 5.15
LON_MIN, LON_MAX = -75.62, -75.38

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class PlaceEntry:
    name: str
    kind: PlaceKind
    lat: float
    lon: float
    barrio: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Location:
    lat: float | None
    lon: float | None
    precision: GeoPrecision
    barrio: str | None
    place_name: str | None

    @property
    def has_point(self) -> bool:
        return self.lat is not None and self.lon is not None


NO_LOCATION = Location(None, None, GeoPrecision.none, None, None)

_PRECISION_BY_KIND: dict[PlaceKind, GeoPrecision] = {
    PlaceKind.referencia: GeoPrecision.address,
    PlaceKind.via: GeoPrecision.barrio,
    PlaceKind.barrio: GeoPrecision.barrio,
    PlaceKind.comuna: GeoPrecision.barrio,
}


def in_manizales(lat: float, lon: float) -> bool:
    return LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


class Gazetteer:
    """Busca la referencia más específica (alias más largo) mencionada en un texto."""

    def __init__(self, entries: list[PlaceEntry]) -> None:
        self.entries = entries
        pairs = [(alias, e) for e in entries for alias in e.aliases if alias]
        # Alias más largos primero: "avenida santander" gana sobre "santander".
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._patterns = [
            (re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"), entry)
            for alias, entry in pairs
        ]
        self._by_alias = {alias: entry for alias, entry in pairs}

    def lookup_token(self, token: str) -> PlaceEntry | None:
        """Lugar de un SMS (`MILAN`, `AV_SANTANDER` ya normalizados)."""
        norm = normalize(token)
        return self._by_alias.get(norm) or self.find(norm)

    def find(self, text: str) -> PlaceEntry | None:
        norm = normalize(text)
        for pattern, entry in self._patterns:
            if pattern.search(norm):
                return entry
        return None


def locate(
    *,
    gazetteer: Gazetteer,
    lat: float | None = None,
    lon: float | None = None,
    gps_precision: GeoPrecision = GeoPrecision.gps,
    barrio: str | None = None,
    place_token: str | None = None,
    text: str = "",
) -> Location:
    """Prioridad: coordenadas válidas > barrio elegido > lugar del SMS > lugar en el texto."""
    if lat is not None and lon is not None and in_manizales(lat, lon):
        found = gazetteer.find(text)
        return Location(lat, lon, gps_precision, found.barrio if found else barrio, None)

    candidates: list[PlaceEntry | None] = []
    if barrio:
        candidates.append(gazetteer.lookup_token(barrio))
    if place_token:
        candidates.append(gazetteer.lookup_token(place_token))
    # Una referencia precisa en el texto mejora un barrio genérico.
    in_text = gazetteer.find(text) if text else None
    for entry in candidates:
        if entry is None:
            continue
        if in_text and in_text.kind == PlaceKind.referencia and in_text.barrio == entry.barrio:
            entry = in_text
        return Location(
            entry.lat, entry.lon, _PRECISION_BY_KIND[entry.kind], entry.barrio, entry.name
        )
    if in_text:
        return Location(
            in_text.lat, in_text.lon, _PRECISION_BY_KIND[in_text.kind], in_text.barrio, in_text.name
        )
    return NO_LOCATION
