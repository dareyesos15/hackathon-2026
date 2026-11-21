"""Trust score 0–100 explicable (FR-018 a FR-020; pesos en CLAUDE.md §7.4).

El desglose se guarda en `Incident.trust_breakdown` y se muestra tal cual en el tablero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.adapters.hazard import PhysicalConsistency
from app.config import TrustWeights
from app.domain import Channel, GeoPrecision, TrustLabel

MODEL_VERSION = "trust-v1"

CHANNEL_RELIABILITY: dict[Channel, float] = {
    Channel.entity: 0.9,
    Channel.lora: 0.6,
    Channel.pwa: 0.5,
    Channel.sms: 0.5,
    Channel.call_123: 0.4,
    Channel.whatsapp: 0.3,
}
CHANNEL_LABEL: dict[Channel, str] = {
    Channel.entity: "entidad oficial",
    Channel.lora: "nodo LoRa",
    Channel.pwa: "app ciudadana",
    Channel.sms: "SMS",
    Channel.call_123: "llamada 123",
    Channel.whatsapp: "WhatsApp reenviado",
}
GEO_POINTS_FRACTION: dict[GeoPrecision, float] = {
    GeoPrecision.gps: 1.0,
    GeoPrecision.address: 0.7,
    GeoPrecision.barrio: 0.5,
    GeoPrecision.none: 0.0,
}
GEO_LABEL: dict[GeoPrecision, str] = {
    GeoPrecision.gps: "GPS",
    GeoPrecision.address: "dirección/referencia",
    GeoPrecision.barrio: "barrio",
    GeoPrecision.none: "sin ubicación",
}
PENALTY_PER_SIGNAL = 7.5


@dataclass(frozen=True)
class ReportSignals:
    channel: Channel
    precision: GeoPrecision
    has_media: bool
    misinfo_signals: Sequence[str]


@dataclass(frozen=True)
class TrustResult:
    score: int
    label: TrustLabel
    breakdown: dict[str, Any]


def label_for(score: float) -> TrustLabel:
    if score >= 75:
        return TrustLabel.verificado
    if score >= 50:
        return TrustLabel.probable
    if score >= 25:
        return TrustLabel.sin_verificar
    return TrustLabel.posible_falso


def _reliability(r: ReportSignals) -> float:
    value = CHANNEL_RELIABILITY[r.channel]
    if r.channel == Channel.pwa and r.precision == GeoPrecision.gps and r.has_media:
        value = 0.6  # PWA con GPS y foto (CLAUDE.md §7.4)
    return value


def _part(puntos: float, maximo: float, detalle: str, minimo: float = 0.0) -> dict[str, Any]:
    part: dict[str, Any] = {"puntos": round(puntos, 2), "max": maximo, "detalle": detalle}
    if minimo:
        part["min"] = minimo
    return part


def compute_trust(
    reports: Sequence[ReportSignals],
    independent_sources: int,
    consistency: PhysicalConsistency,
    w: TrustWeights,
    sensor_confirmed: bool = False,
) -> TrustResult:
    """Suma ponderada de 7 señales sobre los reportes vigentes de un incidente."""
    if reports:
        best = max(reports, key=_reliability)
        channel_pts = w.channel * _reliability(best)
        channels = sorted({CHANNEL_LABEL[r.channel] for r in reports})
        channel_detail = f"mejor canal: {CHANNEL_LABEL[best.channel]} ({_reliability(best):.1f})"
        if len(channels) > 1:
            channel_detail += f"; canales: {', '.join(channels)}"
    else:
        channel_pts, channel_detail = 0.0, "sin reportes vigentes"

    sat = w.sources_saturation
    sources_pts = w.independent_sources * min(independent_sources, sat) / sat
    physical_pts = w.physical_consistency * consistency.value

    best_geo = max(
        (r.precision for r in reports), key=lambda p: GEO_POINTS_FRACTION[p], default=None
    )
    geo_fraction = GEO_POINTS_FRACTION[best_geo] if best_geo else 0.0
    geo_pts = w.geo_precision * geo_fraction

    flagged = [r for r in reports if r.misinfo_signals]
    signal_names = sorted({s for r in reports for s in r.misinfo_signals})
    if reports and flagged:
        per_report = [
            min(-w.misinformation_min, PENALTY_PER_SIGNAL * len(r.misinfo_signals)) for r in reports
        ]
        misinfo_pts = -sum(per_report) / len(reports)
        misinfo_detail = (
            f"{len(flagged)} de {len(reports)} reportes con señales: {', '.join(signal_names)}"
        )
    else:
        misinfo_pts, misinfo_detail = 0.0, "sin señales"

    with_media = any(r.has_media for r in reports)
    evidence_pts = w.evidence if with_media else 0.0
    sensor_pts = w.field_sensor if sensor_confirmed else 0.0

    breakdown: dict[str, Any] = {
        "canal": _part(channel_pts, w.channel, channel_detail),
        "fuentes_independientes": _part(
            sources_pts,
            w.independent_sources,
            f"{independent_sources} fuentes (el máximo se alcanza con {sat})",
        ),
        "consistencia_fisica": _part(physical_pts, w.physical_consistency, consistency.detail),
        "precision_geografica": _part(
            geo_pts, w.geo_precision, GEO_LABEL[best_geo] if best_geo else "sin ubicación"
        ),
        "desinformacion": _part(misinfo_pts, 0, misinfo_detail, minimo=w.misinformation_min),
        "evidencia": _part(evidence_pts, w.evidence, "con foto" if with_media else "sin foto"),
        "sensor_campo": _part(
            sensor_pts, w.field_sensor, "confirmado" if sensor_confirmed else "sin sensor (P1)"
        ),
    }
    total = sum(p["puntos"] for p in breakdown.values())
    total = max(0.0, min(100.0, total))
    score = int(round(total))
    label = label_for(score)  # la etiqueta coincide con el número visible
    breakdown["total"] = round(total, 2)
    breakdown["etiqueta"] = label.value
    breakdown["version_modelo"] = MODEL_VERSION
    return TrustResult(score=score, label=label, breakdown=breakdown)
