"""Trust score 0–100 con desglose (FR-018 a FR-020, CLAUDE.md §7.4)."""

import pytest

from app.adapters.hazard import PhysicalConsistency
from app.config import TrustWeights
from app.core.trust import ReportSignals, compute_trust, label_for
from app.domain import Channel, GeoPrecision, TrustLabel

W = TrustWeights()
NEUTRAL = PhysicalConsistency(0.5, "sin dato de sensor (neutro)", has_data=False)


def sig(**kw: object) -> ReportSignals:
    base: dict[str, object] = dict(
        channel=Channel.sms, precision=GeoPrecision.barrio, has_media=False, misinfo_signals=()
    )
    base.update(kw)
    return ReportSignals(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (0, "posible_falso"),
        (24.9, "posible_falso"),
        (25, "sin_verificar"),
        (49, "sin_verificar"),
        (50, "probable"),
        (74, "probable"),
        (75, "verificado"),
        (100, "verificado"),
    ],
)
def test_labels(score: float, label: str) -> None:
    assert label_for(score) == TrustLabel(label)


def test_breakdown_sums_to_total() -> None:
    result = compute_trust([sig(), sig(channel=Channel.entity)], 2, NEUTRAL, W)
    parts = [v["puntos"] for k, v in result.breakdown.items() if isinstance(v, dict)]
    assert round(sum(parts), 1) == round(result.breakdown["total"], 1)
    assert result.score == round(result.breakdown["total"])


def test_more_independent_sources_raise_score() -> None:
    one = compute_trust([sig()], 1, NEUTRAL, W).score
    three = compute_trust([sig(), sig(), sig()], 3, NEUTRAL, W).score
    assert three > one


def test_misinformation_lowers_score_to_possible_fake() -> None:
    rumor = sig(
        channel=Channel.whatsapp,
        precision=GeoPrecision.none,
        misinfo_signals=("reenvia", "dicen que"),
    )
    result = compute_trust([rumor], 1, NEUTRAL, W)
    assert result.label == TrustLabel.posible_falso
    assert result.breakdown["desinformacion"]["puntos"] < 0


def test_official_entity_with_gps_and_corroboration_is_verified() -> None:
    reports = [
        sig(channel=Channel.entity, precision=GeoPrecision.gps),
        sig(channel=Channel.pwa, precision=GeoPrecision.gps, has_media=True),
        sig(),
        sig(channel=Channel.whatsapp),
    ]
    result = compute_trust(reports, 4, NEUTRAL, W)
    assert result.label == TrustLabel.verificado


def test_score_is_clamped() -> None:
    result = compute_trust([sig(misinfo_signals=("a", "b", "c", "d"))], 0, NEUTRAL, W)
    assert 0 <= result.score <= 100
