"""Gazetteer y ubicación (FR-012)."""

import pytest

from app.core.geo import Gazetteer, PlaceEntry, haversine_m, in_manizales, locate
from app.domain import GeoPrecision, PlaceKind


@pytest.fixture
def gaz() -> Gazetteer:
    return Gazetteer(
        [
            PlaceEntry("Milán", PlaceKind.barrio, 5.0505, -75.4825, "Milán", ("milan",)),
            PlaceEntry(
                "La Enea", PlaceKind.barrio, 5.0302, -75.4652, "La Enea", ("la enea", "enea")
            ),
            PlaceEntry(
                "Avenida Santander",
                PlaceKind.via,
                5.0612,
                -75.5002,
                "Laureles",
                ("avenida santander", "santander"),
            ),
            PlaceEntry(
                "Coliseo Mayor",
                PlaceKind.referencia,
                5.0612,
                -75.5048,
                "Aranjuez",
                ("coliseo mayor", "coliseo"),
            ),
        ]
    )


def test_sms_token(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, place_token="milan")
    assert loc.barrio == "Milán"
    assert loc.precision == GeoPrecision.barrio


def test_text_with_abbreviation(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, text="arbol caido en la av santander")
    assert loc.place_name == "Avenida Santander"


def test_reference_gives_address_precision(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, text="hay atrapados en el Coliseo Mayor")
    assert loc.precision == GeoPrecision.address


def test_gps_inside_city(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, lat=5.05, lon=-75.48, text="en Milán")
    assert loc.precision == GeoPrecision.gps
    assert loc.barrio == "Milán"


def test_gps_outside_city_falls_back(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, lat=4.6, lon=-74.08, text="en La Enea")
    assert loc.barrio == "La Enea"
    assert loc.precision == GeoPrecision.barrio


def test_unknown_place(gaz: Gazetteer) -> None:
    loc = locate(gazetteer=gaz, text="en el puente de oro")
    assert loc.precision == GeoPrecision.none
    assert not loc.has_point


def test_haversine_and_bbox() -> None:
    assert 2400 < haversine_m(5.0689, -75.5174, 5.0505, -75.4825) < 4600
    assert in_manizales(5.0689, -75.5174)
    assert not in_manizales(4.6, -74.08)
