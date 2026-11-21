"""Revisión a predio (formato GUE-RPD-FR-02 v4): semáforo sugerido y coherencia."""

from app.core.recovery import owner_hash, review_inconsistency, suggest_semaphore
from app.domain import DamageLevel, InspectionColor


def test_semaphore_follows_affectation_and_evacuation() -> None:
    assert suggest_semaphore("ninguna", False) == (InspectionColor.verde, DamageLevel.menor)
    assert suggest_semaphore("parcial", False)[0] == InspectionColor.amarillo
    assert suggest_semaphore("parcial", True)[0] == InspectionColor.rojo
    assert suggest_semaphore("total", False)[0] == InspectionColor.rojo


def test_incoherent_reviews_are_rejected() -> None:
    assert review_inconsistency(InspectionColor.amarillo, "parcial", True)
    assert review_inconsistency(InspectionColor.verde, "ninguna", True)
    assert review_inconsistency(InspectionColor.amarillo, "ninguna", False)
    assert review_inconsistency(InspectionColor.amarillo, "total", False)
    assert review_inconsistency(InspectionColor.rojo, "parcial", True) is None
    assert review_inconsistency(InspectionColor.verde, "ninguna", False) is None


def test_owner_hash_never_contains_the_document() -> None:
    digest = owner_hash("1.053.123.456", salt="sal")
    assert "1053123456" not in digest and len(digest) == 64
    assert digest == owner_hash("1053123456", salt="sal")


def test_housing_status_follows_semaphore() -> None:
    from app.core.recovery import housing_status_for

    assert housing_status_for("verde", "menor") == "habitable"
    assert housing_status_for("amarillo", "mediano_uso_restringido") == "habitable"
    assert housing_status_for("rojo", "mayor") == "no_habitable"
    assert housing_status_for("rojo", "colapso") == "destruida"
    assert housing_status_for(None, None) is None
