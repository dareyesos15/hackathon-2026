"""ETA SIMULADA en línea recta (research R5)."""

import pytest

from app.adapters.routing import StraightLineRouting
from app.core.geo import haversine_m


def test_distance_applies_urban_tortuosity() -> None:
    routing = StraightLineRouting(speed_kmh=25.0, tortuosity=1.4)
    straight = haversine_m(5.0682, -75.5160, 5.0505, -75.4825)
    route = routing.estimate(5.0682, -75.5160, 5.0505, -75.4825)
    assert route.distance_m == pytest.approx(straight * 1.4)


def test_duration_uses_fixed_speed() -> None:
    routing = StraightLineRouting(speed_kmh=36.0, tortuosity=1.0)
    route = routing.estimate(5.0, -75.5, 5.0, -75.5)
    assert route.distance_m == 0
    assert route.duration_s == 0
    route = routing.estimate(5.0, -75.5, 5.009, -75.5)  # ~1 km
    assert route.duration_s == pytest.approx(route.distance_m / 10.0)


def test_estimate_is_labeled_simulated() -> None:
    route = StraightLineRouting(speed_kmh=25.0, tortuosity=1.4).estimate(5.0, -75.5, 5.01, -75.5)
    assert route.source == "SIMULADO"
