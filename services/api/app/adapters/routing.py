"""Tiempo estimado de llegada (research R5). Interfaz `RoutingProvider` (principio VI).

Por defecto: línea recta × tortuosidad urbana a velocidad fija, etiquetado SIMULADO. El API de
rutas con probabilidad de bloqueo de ERIS-UNAL (grupo innovaTE) será otra implementación.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.config import Settings
from app.core.geo import haversine_m


@dataclass(frozen=True)
class RouteEstimate:
    distance_m: float
    duration_s: float
    source: str = "SIMULADO"


class RoutingProvider(Protocol):
    def estimate(
        self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
    ) -> RouteEstimate: ...


class StraightLineRouting:
    """Distancia haversine × tortuosidad, a `speed_kmh` constantes. Sin red vial."""

    def __init__(self, speed_kmh: float, tortuosity: float) -> None:
        self._speed_ms = speed_kmh / 3.6
        self._tortuosity = tortuosity

    def estimate(
        self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
    ) -> RouteEstimate:
        distance = haversine_m(origin_lat, origin_lon, dest_lat, dest_lon) * self._tortuosity
        return RouteEstimate(distance_m=distance, duration_s=distance / self._speed_ms)


def build_routing(settings: Settings) -> RoutingProvider:
    return StraightLineRouting(settings.routing_speed_kmh, settings.routing_tortuosity)
