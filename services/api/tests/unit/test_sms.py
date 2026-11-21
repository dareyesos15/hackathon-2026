"""Parser del SMS compacto (contracts/sms-format.md, FR-004)."""

from app.core.sms import parse_sms
from app.domain import Category


def test_full_sms_with_barrio() -> None:
    sms = parse_sms("DACORA ATR MILAN 3 edificio caido cra 23")
    assert sms.has_prefix
    assert sms.category == Category.personas_atrapadas
    assert sms.place_token == "milan"
    assert sms.coords is None
    assert sms.people == 3
    assert sms.text == "edificio caido cra 23"


def test_lowercase_prefix_and_coordinates() -> None:
    sms = parse_sms("dacora gas 5.0689,-75.5174 0 huele mucho a gas")
    assert sms.category == Category.fuga_gas
    assert sms.coords == (5.0689, -75.5174)
    assert sms.people == 0
    assert sms.text == "huele mucho a gas"


def test_unknown_code_keeps_place_and_text() -> None:
    sms = parse_sms("DACORA XYZ CHIPRE se cayo una pared")
    assert sms.has_prefix
    assert sms.category is None
    assert sms.place_token == "chipre"
    assert sms.people is None
    assert sms.text == "se cayo una pared"


def test_underscore_place_becomes_spaces() -> None:
    sms = parse_sms("DACORA VIA AV_SANTANDER 0 arbol caido")
    assert sms.category == Category.via_bloqueada
    assert sms.place_token == "av santander"


def test_without_prefix_is_free_text() -> None:
    sms = parse_sms("ayuda en la enea")
    assert not sms.has_prefix
    assert sms.category is None
    assert sms.place_token is None
    assert sms.text == "ayuda en la enea"


def test_too_long_is_flagged() -> None:
    sms = parse_sms("DACORA DAN CENTRO 1 " + "x" * 200)
    assert sms.too_long


def test_all_codes_map_to_categories() -> None:
    codes = ["ATR", "HER", "COL", "DAN", "INC", "GAS", "DES", "VIA", "SER", "ALB", "AYU", "DSP"]
    assert all(parse_sms(f"DACORA {c} CENTRO 1 texto").category is not None for c in codes)
