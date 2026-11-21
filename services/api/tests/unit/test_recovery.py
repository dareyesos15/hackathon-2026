"""Reglas puras del módulo de recuperación (specs/003): predio único, hogar y ayudas."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.recovery import (
    consistent,
    household_hash,
    is_duplicate_aid,
    normalize_address,
    property_key,
    suppress,
)
from app.domain import AidType, DamageLevel, InspectionColor

SALT = "sal-de-prueba"
NOW = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "address",
    ["Cra. 23 # 45-10", "carrera 23 45 10", "KR 23 No. 45 - 10", "cr 23 nro 45-10"],
)
def test_address_variants_normalize_to_same_form(address: str) -> None:
    assert normalize_address(address) == "carrera 23 45 10"


def test_same_property_written_differently_gets_one_key() -> None:
    a = property_key(cadastral_code=None, manzana_id="M001", address="Cra. 23 # 45-10")
    b = property_key(cadastral_code=None, manzana_id="M001", address="carrera 23 45 10")
    assert a == b == "M001:carrera 23 45 10"


def test_cadastral_code_wins_over_address() -> None:
    key = property_key(cadastral_code="17-001-01.02", manzana_id="M001", address="calle 1")
    assert key == "CAT:170010102"


def test_property_without_code_nor_address_is_rejected() -> None:
    with pytest.raises(ValueError):
        property_key(cadastral_code=None, manzana_id="M001", address=None)
    with pytest.raises(ValueError):
        property_key(cadastral_code="  ", manzana_id=None, address="carrera 23")


def test_household_hash_ignores_formatting_and_hides_document() -> None:
    a = household_hash("1.053.123.456", salt=SALT)
    b = household_hash("1053123456", salt=SALT)
    assert a == b
    assert "1053123456" not in a
    assert len(a) == 64


def test_household_hash_depends_on_salt() -> None:
    assert household_hash("1053123456", salt=SALT) != household_hash("1053123456", salt="otra")


def test_short_document_is_rejected() -> None:
    with pytest.raises(ValueError):
        household_hash("12-3", salt=SALT)


@pytest.mark.parametrize(
    ("color", "damage", "ok"),
    [
        (InspectionColor.verde, DamageLevel.menor, True),
        (InspectionColor.verde, DamageLevel.colapso, False),
        (InspectionColor.amarillo, DamageLevel.mediano_uso_restringido, True),
        (InspectionColor.amarillo, DamageLevel.mayor, False),
        (InspectionColor.rojo, DamageLevel.colapso, True),
        (InspectionColor.rojo, DamageLevel.menor, False),
    ],
)
def test_traffic_light_must_match_damage(
    color: InspectionColor, damage: DamageLevel, ok: bool
) -> None:
    assert consistent(color, damage) is ok


def test_same_aid_inside_window_is_duplicate() -> None:
    previous = [NOW - timedelta(days=3)]
    assert is_duplicate_aid(AidType.mercado, previous, NOW)
    assert is_duplicate_aid(AidType.kit, previous, NOW)


def test_same_aid_after_window_is_allowed() -> None:
    assert not is_duplicate_aid(AidType.mercado, [NOW - timedelta(days=8)], NOW)
    assert not is_duplicate_aid(AidType.subsidio_arriendo, [NOW - timedelta(days=31)], NOW)
    assert not is_duplicate_aid(AidType.kit, [], NOW)


def test_public_figures_below_k_are_suppressed() -> None:
    assert suppress(4, 5) is None
    assert suppress(5, 5) == 5
