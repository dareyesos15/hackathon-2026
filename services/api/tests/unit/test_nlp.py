"""Clasificación, triaje y señales de desinformación (FR-010, FR-011, research R6)."""

import pytest

from app.core.nlp import classify
from app.domain import Category, TriageLevel


@pytest.mark.parametrize(
    ("text", "category", "triage"),
    [
        ("edificio caido cra 23, hay gente atrapada", Category.personas_atrapadas, "critico"),
        ("quedaron personas bajo los escombros en Milán", Category.personas_atrapadas, "critico"),
        ("hay dos heridos sangrando en la esquina", Category.heridos, "critico"),
        ("se cayó la casa con la familia adentro", Category.colapso_estructura, "critico"),
        ("se derrumbó una casa vacía en Chipre", Category.colapso_estructura, "alto"),
        ("grietas grandes en las columnas del edificio", Category.dano_estructural, "alto"),
        ("una fisura pequeña en la pared, daño leve", Category.dano_estructural, "bajo"),
        ("se cayeron unas tejas del techo", Category.dano_estructural, "medio"),
        ("hay fuego y mucho humo en la bodega", Category.incendio, "critico"),
        ("huele muchísimo a gas en el edificio", Category.fuga_gas, "critico"),
        ("deslizamiento tapó dos viviendas en la ladera", Category.deslizamiento, "critico"),
        ("se vino el talud sobre la vía", Category.deslizamiento, "alto"),
        ("derrumbe de tierra en la ladera, afectó viviendas", Category.deslizamiento, "critico"),
        ("se cayó la torre del Cable Aéreo", Category.colapso_estructura, "alto"),
        ("la vía al hospital está bloqueada por escombros", Category.via_bloqueada, "alto"),
        ("sin luz ni agua en todo el barrio", Category.servicios_caidos, "medio"),
        ("necesitamos albergue, quedamos sin casa", Category.necesidad_albergue, "medio"),
        ("necesitamos agua y comida para 20 familias", Category.necesidad_ayuda, "medio"),
        ("mi hermano no aparece desde el sismo", Category.persona_desaparecida, "alto"),
        ("se sintió muy fuerte el temblor, qué susto", Category.sismo_sentido, "bajo"),
    ],
)
def test_category_and_triage(text: str, category: Category, triage: str) -> None:
    result = classify(text)
    assert result.category == category
    assert result.triage_level == TriageLevel(triage)


def test_life_threat_only_for_critical() -> None:
    assert classify("hay gente atrapada").is_life_threat
    assert classify("huele a gas").is_life_threat
    assert not classify("sin luz en el barrio").is_life_threat
    assert not classify("se sintió el temblor").is_life_threat


def test_hint_overrides_lexicon() -> None:
    result = classify("edificio caido cra 23", hint=Category.personas_atrapadas, people=3)
    assert result.category == Category.personas_atrapadas
    assert result.is_life_threat


def test_rumor_with_chain_language() -> None:
    result = classify("reenvia urgente dicen que habra replica de 9 a las 3 pm")
    assert result.category == Category.rumor_informacion
    assert result.triage_level == TriageLevel.bajo
    assert {"reenvia", "dicen que", "replica de 9"} <= set(result.misinfo_signals)


def test_fake_infrastructure_chain_becomes_rumor() -> None:
    result = classify("URGENTE COMPARTIR: se cayó el puente de la Avenida Santander")
    assert result.category == Category.rumor_informacion
    assert "urgente compartir" in result.misinfo_signals


def test_critical_hearsay_stays_critical_with_signals() -> None:
    result = classify("dicen que hay atrapados en el Coliseo Mayor")
    assert result.category == Category.personas_atrapadas
    assert result.is_life_threat
    assert "dicen que" in result.misinfo_signals


def test_unknown_text_is_unclassified_medium() -> None:
    result = classify("hola buenas")
    assert result.category == Category.sin_clasificar
    assert result.triage_level == TriageLevel.medio


def test_severity_matches_triage() -> None:
    assert classify("hay gente atrapada").severity == 5
    assert classify("se sintió el temblor").severity == 1
