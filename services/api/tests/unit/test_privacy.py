"""Redacción de datos personales y HMAC (principio I, FR-006, FR-007)."""

import json

import pytest

from app.config import get_settings
from app.core.privacy import contains_pii, redact, reporter_hash

CASES = json.loads((get_settings().data_dir / "fixtures" / "pii_cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["input"][:40] for c in CASES])
def test_redact_matches_shared_fixture(case: dict[str, str]) -> None:
    assert redact(case["input"]).text == case["expected"]


@pytest.mark.parametrize("case", CASES, ids=[c["input"][:40] for c in CASES])
def test_redacted_text_has_no_pii(case: dict[str, str]) -> None:
    assert not contains_pii(redact(case["input"]).text)


def test_redact_reports_kinds() -> None:
    result = redact("me llamo Ana, cel 3001234567, correo a@b.co")
    assert set(result.kinds) == {"NOMBRE", "TEL", "CORREO"}


def test_hash_is_stable_and_normalized() -> None:
    a = reporter_hash("+57 300 123 4567", salt="sal-de-prueba")
    b = reporter_hash("3001234567", salt="sal-de-prueba")
    assert a == b
    assert len(a) == 64
    assert "3001234567" not in a


def test_hash_depends_on_salt() -> None:
    assert reporter_hash("3001234567", salt="sal-uno-xx") != reporter_hash(
        "3001234567", salt="sal-dos-xx"
    )


def test_hash_of_empty_is_none() -> None:
    assert reporter_hash("", salt="sal-de-prueba") is None
    assert reporter_hash(None, salt="sal-de-prueba") is None
