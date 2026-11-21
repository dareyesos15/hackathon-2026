"""Agrupación de reportes en incidentes: reglas puras (FR-014 a FR-016)."""

import uuid
from datetime import UTC, datetime, timedelta

from app.config import DedupSettings
from app.core.dedup import (
    Candidate,
    ReportCtx,
    address_signature,
    choose_incident,
    compatible,
    independent_sources,
    weighted_centroid,
)
from app.core.similarity import TfidfSimilarity
from app.domain import Category, Channel, GeoPrecision

T0 = datetime(2026, 8, 10, 12, 34, tzinfo=UTC)
CFG = DedupSettings()
SIM = TfidfSimilarity()


def report(**kw: object) -> ReportCtx:
    base: dict[str, object] = dict(
        category=Category.personas_atrapadas,
        lat=5.0505,
        lon=-75.4825,
        precision=GeoPrecision.barrio,
        occurred_at=T0 + timedelta(minutes=40),
        text="se cayo el edificio de la carrera 23 en milan, hay gente atrapada",
        reporter_hash="b" * 64,
    )
    base.update(kw)
    return ReportCtx(**base)  # type: ignore[arg-type]


def candidate(**kw: object) -> Candidate:
    base: dict[str, object] = dict(
        incident_id=uuid.uuid4(),
        category=Category.personas_atrapadas,
        lat=5.0507,
        lon=-75.4827,
        precision=GeoPrecision.barrio,
        first_seen=T0,
        last_seen=T0,
        texts=["edificio caido carrera 23 milan personas atrapadas"],
    )
    base.update(kw)
    return Candidate(**base)  # type: ignore[arg-type]


def test_same_event_from_other_source_joins() -> None:
    cand = candidate()
    match = choose_incident(report(), [cand], SIM, CFG)
    assert match is not None and match.incident_id == cand.incident_id


def test_different_category_same_block_does_not_join() -> None:
    cand = candidate(category=Category.incendio, texts=["incendio en la bodega de milan"])
    r = report(category=Category.via_bloqueada, text="via bloqueada por escombros en milan")
    assert choose_incident(r, [cand], SIM, CFG) is None


def test_compatible_categories() -> None:
    assert compatible(Category.colapso_estructura, Category.personas_atrapadas)
    assert compatible(Category.fuga_gas, Category.incendio)
    assert not compatible(Category.incendio, Category.via_bloqueada)
    assert compatible(Category.necesidad_ayuda, Category.necesidad_ayuda)


def test_outside_time_window_creates_new() -> None:
    cand = candidate(last_seen=T0)
    r = report(occurred_at=T0 + timedelta(hours=3, minutes=30))
    assert choose_incident(r, [cand], SIM, CFG) is None


def test_too_far_creates_new() -> None:
    cand = candidate(lat=5.0689, lon=-75.5174)  # Centro, ~4 km
    assert choose_incident(report(), [cand], SIM, CFG) is None


def test_no_location_rumors_join_by_text() -> None:
    text = "reenvia urgente dicen que habra replica de 9 a las 3 pm"
    cand = candidate(
        category=Category.rumor_informacion,
        lat=None,
        lon=None,
        precision=GeoPrecision.none,
        texts=[text],
    )
    r = report(
        category=Category.rumor_informacion,
        lat=None,
        lon=None,
        precision=GeoPrecision.none,
        text="URGENTE dicen que a las 3 pm habra replica de 9, reenvia",
    )
    match = choose_incident(r, [cand], SIM, CFG)
    assert match is not None


def test_independent_sources_ignores_repeated_sender() -> None:
    h = "a" * 64
    rows = [(h, Channel.sms, False), (h, Channel.sms, False), (h, Channel.sms, False)]
    assert independent_sources(rows) == 1
    rows.append(("c" * 64, Channel.whatsapp, False))
    rows.append((None, Channel.entity, False))
    assert independent_sources(rows) == 3


def test_forwarded_chains_do_not_corroborate() -> None:
    chains = [("x" * 64, Channel.whatsapp, True), ("y" * 64, Channel.whatsapp, True)]
    assert independent_sources(chains) == 1
    assert independent_sources([*chains, ("z" * 64, Channel.sms, False)]) == 1


def test_weighted_centroid_prefers_gps() -> None:
    lat, lon = weighted_centroid(
        [(5.0, -75.0, GeoPrecision.gps), (5.1, -75.1, GeoPrecision.barrio)]
    )
    assert abs(lat - 5.0) < abs(lat - 5.1)


def test_address_signature() -> None:
    sig = address_signature("grietas en la cra 23 con calle 43, Centro")
    assert sig == frozenset({"carrera 23", "calle 43"})


def test_same_intersection_joins_despite_coarse_location() -> None:
    cand = candidate(
        category=Category.heridos,
        lat=5.0668,
        lon=-75.5142,
        texts=["hay 4 heridos en la calle 30 con carrera 24, Centro, necesitamos ambulancia"],
    )
    r = report(
        category=Category.heridos,
        lat=5.0689,
        lon=-75.5174,
        text="4 lesionados frente al edificio de la carrera 24 con calle 30",
    )
    assert choose_incident(r, [cand], SIM, CFG) is not None


def test_different_intersection_never_joins() -> None:
    cand = candidate(texts=["se cayo el edificio de la calle 30 con carrera 23, hay atrapados"])
    r = report(text="se cayo el edificio de la calle 45 con carrera 23, hay atrapados")
    assert choose_incident(r, [cand], SIM, CFG) is None


def test_same_intersection_wins_over_more_similar_neighbor() -> None:
    same = candidate(texts=["se cayo el colegio de la calle 30 con carrera 23, gente atrapada"])
    other = candidate(texts=["se cayo el edificio en milan hay gente atrapada adentro"])
    r = report(text="hay gente atrapada en el edificio de la carrera 23 con calle 30 en milan")
    match = choose_incident(r, [other, same], SIM, CFG)
    assert match is not None and match.incident_id == same.incident_id
