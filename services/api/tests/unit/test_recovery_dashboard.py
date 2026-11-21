"""Reglas del tablero de recuperación unificado (índice, etapas, situación de hogares)."""

from app.core.recovery_dashboard import (
    SERVICES,
    STAGES,
    habitability_score,
    household_situation,
    load_context,
    recovery_index,
    services_score,
    stage_status,
)


def test_habitability_counts_restricted_use_as_half() -> None:
    assert habitability_score(verde=2, amarillo=2, rojo=0) == 75.0
    assert habitability_score(0, 0, 0) is None


def test_index_ignores_components_without_data() -> None:
    assert recovery_index({"habitabilidad": 40.0, "servicios": 80.0, "familias": None}) == 60.0
    assert recovery_index({"habitabilidad": None}) is None


def test_household_situation_flags_red_property_without_housing() -> None:
    assert household_situation("albergue", "rojo") == "albergue"
    assert household_situation("subsidio_arriendo", "rojo") == "arriendo"
    assert household_situation(None, "rojo") == "sin_solucion"
    assert household_situation(None, "amarillo") == "casa"
    assert household_situation(None, None) == "casa"


def test_stage_status_follows_expected_progress() -> None:
    stage = STAGES[3]  # reactivación, días 15 a 60
    assert stage_status(10, stage, 0.0) == "pendiente"
    assert stage_status(60, stage, 0.95) == "verde"
    assert stage_status(60, stage, 0.7) == "amarillo"
    assert stage_status(60, stage, 0.3) == "rojo"
    # A mitad de la ventana se espera ~50 %.
    assert stage_status(37, stage, 0.5) == "verde"


def test_context_covers_every_barrio_and_service() -> None:
    ctx = load_context()
    assert len(ctx["services"]) == len(ctx["visit_requests"]) >= 40
    row = next(iter(ctx["services"].values()))
    assert all(0 <= row[s] <= 100 for s in SERVICES)
    assert services_score(row) is not None
    assert "SIMULADO" in ctx["note"]
