"""Reglas puras del despacho (specs/002 US1, research R2–R4, data-model.md §Despacho)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.routing import StraightLineRouting
from app.core.dispatch import (
    EMRE_ROUTING,
    DispatchError,
    ResourceView,
    next_status,
    planned_checkpoints,
    rank_candidates,
    resource_status_after,
    routing_for,
    should_move,
)
from app.domain import Category, DispatchStatus, EmreFunction, ResourceStatus, Role

EXPECTED = {
    Category.personas_atrapadas: (EmreFunction.salvamento_seguridad, "BOMBEROS"),
    Category.incendio: (EmreFunction.salvamento_seguridad, "BOMBEROS"),
    Category.fuga_gas: (EmreFunction.salvamento_seguridad, "BOMBEROS"),
    Category.colapso_estructura: (EmreFunction.salvamento_seguridad, "BOMBEROS"),
    Category.heridos: (EmreFunction.salud_saneamiento, "CRUZ_ROJA"),
    Category.necesidad_albergue: (EmreFunction.asistencia_social, "SEC_DESARROLLO_SOCIAL"),
    Category.necesidad_ayuda: (EmreFunction.asistencia_social, "SEC_DESARROLLO_SOCIAL"),
    Category.persona_desaparecida: (EmreFunction.asistencia_social, "SEC_DESARROLLO_SOCIAL"),
    Category.dano_estructural: (EmreFunction.infraestructura_servicios, "SEC_INFRAESTRUCTURA"),
    Category.via_bloqueada: (EmreFunction.infraestructura_servicios, "SEC_INFRAESTRUCTURA"),
    Category.servicios_caidos: (EmreFunction.infraestructura_servicios, "SEC_INFRAESTRUCTURA"),
    Category.deslizamiento: (EmreFunction.infraestructura_servicios, "SEC_INFRAESTRUCTURA"),
}
NO_FUNCTION = {Category.sismo_sentido, Category.rumor_informacion, Category.sin_clasificar}

ROUTING = StraightLineRouting(speed_kmh=25.0, tortuosity=1.4)
INCIDENT = (5.0505, -75.4825)  # Milán


def _res(code: str, agency: str, lat: float, lon: float, status: str = "disponible"):
    return ResourceView(
        id=code, code=code, agency_code=agency, lat=lat, lon=lon, status=ResourceStatus(status)
    )


def test_emre_table_covers_every_category() -> None:
    assert set(EXPECTED) | NO_FUNCTION == set(Category)
    for category, (function, agency) in EXPECTED.items():
        got_function, agencies = routing_for(category)
        assert got_function == function, category
        assert agencies[0] == agency, category
    for category in NO_FUNCTION:
        assert routing_for(category) == (None, ())


def test_alternatives_belong_to_same_function() -> None:
    assert EMRE_ROUTING[Category.personas_atrapadas][1] == ("BOMBEROS", "DEFENSA_CIVIL", "POLICIA")
    assert EMRE_ROUTING[Category.heridos][1] == ("CRUZ_ROJA", "SEC_SALUD")


def test_candidates_of_suggested_agency_sorted_by_distance() -> None:
    resources = [
        _res("BOM-M1", "BOMBEROS", 5.0682, -75.5160),  # Centro, lejos
        _res("BOM-M3", "BOMBEROS", 5.0548, -75.4885),  # Palermo, cerca
        _res("DC-R1", "DEFENSA_CIVIL", 5.0505, -75.4826),  # más cerca, pero alternativa
        _res("BOM-R1", "BOMBEROS", 5.0684, -75.5163, status="en_camino"),  # ocupado
    ]
    ranked, fallback = rank_candidates(*INCIDENT, resources, ("BOMBEROS", "DEFENSA_CIVIL"), ROUTING)
    assert fallback is False
    assert [c.resource.code for c in ranked] == ["BOM-M3", "BOM-M1"]
    assert ranked[0].distance_m < ranked[1].distance_m
    assert ranked[0].eta_min > 0


def test_fallback_to_alternative_agencies_when_none_available() -> None:
    resources = [
        _res("CR-A1", "CRUZ_ROJA", 5.0641, -75.5004, status="en_sitio"),
        _res("SS-A1", "SEC_SALUD", 5.0638, -75.4992),
    ]
    ranked, fallback = rank_candidates(*INCIDENT, resources, ("CRUZ_ROJA", "SEC_SALUD"), ROUTING)
    assert fallback is True
    assert [c.resource.code for c in ranked] == ["SS-A1"]


def test_without_function_lists_every_available_resource() -> None:
    resources = [_res("POL-P2", "POLICIA", 5.0507, -75.4828), _res("CHEC-T1", "CHEC", 5.05, -75.5)]
    ranked, fallback = rank_candidates(*INCIDENT, resources, (), ROUTING)
    assert fallback is False
    assert {c.resource.code for c in ranked} == {"POL-P2", "CHEC-T1"}


@pytest.mark.parametrize(
    ("current", "action", "role", "expected"),
    [
        (DispatchStatus.en_camino, "llegada", Role.agencia, DispatchStatus.en_sitio),
        (DispatchStatus.en_sitio, "finalizar", Role.agencia, DispatchStatus.finalizado),
        (DispatchStatus.en_camino, "cancelar", Role.operador_pmu, DispatchStatus.cancelado),
        (DispatchStatus.en_sitio, "cancelar", Role.coe, DispatchStatus.cancelado),
        (DispatchStatus.en_camino, "fuera_de_servicio", Role.agencia, DispatchStatus.cancelado),
    ],
)
def test_valid_transitions(current, action, role, expected) -> None:
    assert next_status(current, action, role, note="motivo") == expected


@pytest.mark.parametrize(
    ("current", "action", "role", "note", "code"),
    [
        (DispatchStatus.en_camino, "finalizar", Role.agencia, None, "invalid_transition"),
        (DispatchStatus.finalizado, "llegada", Role.agencia, None, "invalid_transition"),
        (DispatchStatus.cancelado, "cancelar", Role.coe, "x", "invalid_transition"),
        (DispatchStatus.en_camino, "cancelar", Role.agencia, "x", "forbidden"),
        (DispatchStatus.en_camino, "cancelar", Role.operador_pmu, "  ", "note_required"),
        (DispatchStatus.en_sitio, "fuera_de_servicio", Role.agencia, None, "note_required"),
    ],
)
def test_invalid_transitions(current, action, role, note, code) -> None:
    with pytest.raises(DispatchError) as err:
        next_status(current, action, role, note=note)
    assert err.value.code == code


def test_resource_status_follows_dispatch() -> None:
    assert resource_status_after("llegada") == ResourceStatus.en_sitio
    assert resource_status_after("finalizar") == ResourceStatus.disponible
    assert resource_status_after("cancelar") == ResourceStatus.disponible
    assert resource_status_after("fuera_de_servicio") == ResourceStatus.fuera_de_servicio


def test_position_moves_only_with_newer_track() -> None:
    t0 = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
    assert should_move(None, t0)
    assert should_move(t0, t0 + timedelta(seconds=1))
    assert not should_move(t0, t0)
    assert not should_move(t0, t0 - timedelta(minutes=1))


def test_planned_checkpoints_compress_eta_with_speedup() -> None:
    start = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
    eta = start + timedelta(minutes=6)
    plan = planned_checkpoints(start, eta, speedup=20.0)
    assert [kind for kind, _, _ in plan] == ["control", "control", "llegada"]
    assert [round(f, 3) for _, f, _ in plan] == [0.333, 0.667, 1.0]
    assert plan[-1][2] == start + timedelta(seconds=18)
