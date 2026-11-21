"""A quién le llega cada incidente y plan multiagencia (app/core/recipients.py)."""

import uuid
from typing import Any

import pytest

from app.core.dispatch import EMRE_ROUTING
from app.core.recipients import Routing, Unit, build_plan, detect_utilities, route_incident
from app.domain import Category, RecipientRole, TriageLevel, TrustLabel

LIFE = {
    Category.personas_atrapadas,
    Category.colapso_estructura,
    Category.incendio,
    Category.fuga_gas,
}


def _route(category: Category, **kw: Any) -> Routing:
    args: dict[str, Any] = {
        "triage": TriageLevel.medio,
        "is_life_threat": category in LIFE,
        "trust_label": TrustLabel.probable,
    }
    args.update(kw)
    return route_incident(category=category, **args)


@pytest.mark.parametrize("category", list(EMRE_ROUTING))
def test_every_routed_category_has_exactly_one_lead(category: Category) -> None:
    routing = _route(category, texts=["sin agua en el sector"])
    leads = [r for r in routing.recipients if r.role == RecipientRole.lider]
    assert len(leads) == 1
    assert len({r.agency for r in routing.recipients}) == len(routing.recipients)
    assert all(r.task[0].isdigit() for r in routing.recipients)  # cita la tarea EMRE


def test_trapped_people_reach_rescue_health_and_police() -> None:
    routing = _route(Category.personas_atrapadas, triage=TriageLevel.critico)
    roles = {r.agency: r.role for r in routing.recipients}
    assert roles["BOMBEROS"] == RecipientRole.lider
    assert roles["CRUZ_ROJA"] == RecipientRole.apoyo
    assert roles["POLICIA"] == RecipientRole.apoyo
    assert routing.notify_coe and not routing.held


def test_gas_leak_involves_utility_and_cuts_power() -> None:
    routing = _route(Category.fuga_gas, triage=TriageLevel.critico)
    roles = {r.agency: r.role for r in routing.recipients}
    assert roles["BOMBEROS"] == RecipientRole.lider
    assert roles["EFIGAS"] == RecipientRole.apoyo
    assert roles["CHEC"] == RecipientRole.informada


@pytest.mark.parametrize(
    ("text", "lead"),
    [
        ("Llevamos 5 horas sin agua en el barrio", "AGUAS_MANIZALES"),
        ("Se fue la luz, hay un poste caído", "CHEC"),
        ("No llega el gas domiciliario", "EFIGAS"),
    ],
)
def test_service_outage_goes_to_the_right_utility(text: str, lead: str) -> None:
    routing = _route(Category.servicios_caidos, texts=[text])
    assert routing.lead is not None and routing.lead.agency == lead
    infra = routing.for_agency("SEC_INFRAESTRUCTURA")
    assert infra is not None and infra.role == RecipientRole.informada


def test_unknown_service_informs_all_utilities() -> None:
    routing = _route(Category.servicios_caidos, texts=["no hay servicio"])
    assert routing.lead is not None and routing.lead.agency == "SEC_INFRAESTRUCTURA"
    informed = {r.agency for r in routing.recipients if r.role == RecipientRole.informada}
    assert informed == {"AGUAS_MANIZALES", "CHEC", "EFIGAS"}
    assert routing.notes


def test_detect_utilities_ignores_accents() -> None:
    assert detect_utilities(["Sin energía eléctrica"]) == ["CHEC"]


def test_low_trust_without_life_threat_is_held() -> None:
    routing = _route(Category.dano_estructural, trust_label=TrustLabel.posible_falso)
    assert routing.held and routing.hold_reason


def test_low_trust_life_threat_is_never_held() -> None:
    routing = _route(
        Category.personas_atrapadas,
        triage=TriageLevel.critico,
        trust_label=TrustLabel.posible_falso,
    )
    assert not routing.held
    assert any("riesgo vital" in n for n in routing.notes)


def test_rumor_goes_only_to_coe() -> None:
    routing = _route(Category.rumor_informacion, triage=TriageLevel.bajo)
    assert routing.recipients == ()
    assert routing.notify_coe and routing.coe_reason and "5.2" in routing.coe_reason


def test_felt_quake_reaches_nobody() -> None:
    routing = _route(Category.sismo_sentido, triage=TriageLevel.bajo)
    assert routing.recipients == () and not routing.notify_coe


def test_severe_injuries_escalate() -> None:
    routing = _route(Category.heridos, triage=TriageLevel.critico, people_affected=6)
    roles = {r.agency: r.role for r in routing.recipients}
    assert roles["SEC_SALUD"] == RecipientRole.apoyo
    assert roles["BOMBEROS"] == RecipientRole.apoyo


def _unit(agency: str, distance: float) -> Unit:
    return Unit(uuid.uuid4(), agency, distance, distance / 500)


def test_plan_picks_nearest_unit_per_agency_and_skips_informed() -> None:
    routing = _route(Category.fuga_gas, triage=TriageLevel.critico)
    near, far = _unit("BOMBEROS", 300), _unit("BOMBEROS", 900)
    units = sorted(
        [far, near, _unit("EFIGAS", 1200), _unit("POLICIA", 500), _unit("CHEC", 100)],
        key=lambda u: u.distance_m,
    )
    plan = build_plan(routing, units, [])
    agencies = [line.recipient.agency for line in plan]
    assert agencies == ["BOMBEROS", "EFIGAS", "POLICIA"]  # CHEC solo queda informada
    assert plan[0].unit == near


def test_plan_sends_two_lead_units_for_many_people() -> None:
    routing = _route(Category.personas_atrapadas, triage=TriageLevel.critico, people_affected=8)
    assert routing.lead_units == 2
    units = [_unit("BOMBEROS", 100), _unit("BOMBEROS", 200), _unit("BOMBEROS", 300)]
    plan = build_plan(routing, units, [])
    assert [line.unit for line in plan if line.recipient.agency == "BOMBEROS"] == units[:2]


def test_plan_skips_agencies_already_dispatched_and_flags_missing() -> None:
    routing = _route(Category.fuga_gas, triage=TriageLevel.critico)
    plan = build_plan(routing, [_unit("POLICIA", 400)], ["BOMBEROS"])
    by_agency = {line.recipient.agency: line for line in plan}
    assert by_agency["BOMBEROS"].already_dispatched and by_agency["BOMBEROS"].unit is None
    assert by_agency["EFIGAS"].unit is None and not by_agency["EFIGAS"].already_dispatched
    assert by_agency["POLICIA"].unit is not None
