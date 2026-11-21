"""Escenarios SIMULADOS de acceso a datos: verdad, observación y estadísticas de confianza."""

import random

from app.core.scenarios import (
    SCENARIOS,
    accurate,
    emre_cadence_h,
    index_from,
    observe,
    simulate,
    truth,
)


def test_emre_cadence_by_day() -> None:
    assert emre_cadence_h(0) == 6.0
    assert emre_cadence_h(4) == 12.0
    assert emre_cadence_h(40) == 24.0


def test_truth_is_consistent() -> None:
    rows = {t.key: t.value for t in truth(102)}
    colors = sum(rows[f"predios_{c}"] for c in ("verde", "amarillo", "rojo", "colapso"))
    assert abs(colors - rows["predios_evaluados"]) < 1e-6
    families = sum(rows[f"familias_{k}"] for k in ("albergue", "arriendo", "casa", "sin_solucion"))
    assert abs(families - rows["familias_unicas"]) < 1e-6
    assert all(0 <= rows[f"servicio_{s}"] <= 100 for s in ("agua", "energia", "gas"))
    assert rows["pagado"] <= rows["contratado"] <= rows["comprometido"] <= rows["recursos"]
    assert index_from(rows) is not None


def test_tolerance_rules() -> None:
    assert accurate("count", 105, 100) and not accurate("count", 115, 100)
    assert accurate("pct", 84, 80) and not accurate("pct", 90, 80)


def test_unavailable_source_yields_no_value() -> None:
    p = SCENARIOS["peor"]
    for seed in range(50):
        obs = observe(p, 30, random.Random(seed))
        for t in truth(30):
            if not obs.source_up[t.source]:
                assert obs.values[t.key] is None


def test_simulation_is_reproducible() -> None:
    a = simulate("peor", 60, runs=200)
    b = simulate("peor", 60, runs=200)
    assert a.stats == b.stats


def test_best_case_is_far_more_reliable_than_worst() -> None:
    best = simulate("mejor", 60, runs=400)
    worst = simulate("peor", 60, runs=400)
    conf = {s.key: s for s in best.stats}["confianza"]
    conf_w = {s.key: s for s in worst.stats}["confianza"]
    assert conf.mean > 85 > 40 > conf_w.mean
    assert conf.p5 > conf_w.p95  # los intervalos no se cruzan
    assert best.p_high_confidence > 90 and worst.p_high_confidence < 5
