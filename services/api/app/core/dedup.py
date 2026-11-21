"""Agrupación de reportes en incidentes (FR-014 a FR-017, research R1/R10).

Duplicado ≠ basura: el reporte duplicado suma corroboración y completa datos del incidente.
Reglas puras arriba; consultas a PostGIS abajo.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DedupSettings
from app.core.geo import haversine_m
from app.core.similarity import SimilarityProvider
from app.core.text import normalize
from app.domain import (
    TRIAGE_RANK,
    Category,
    Channel,
    GeoPrecision,
    IncidentStatus,
    ReportStatus,
)
from app.models import Incident, Report

COMPATIBLE_GROUPS: tuple[frozenset[Category], ...] = (
    frozenset(
        {
            Category.personas_atrapadas,
            Category.colapso_estructura,
            Category.dano_estructural,
            Category.heridos,
        }
    ),
    frozenset({Category.fuga_gas, Category.incendio}),
    frozenset({Category.deslizamiento, Category.via_bloqueada}),
)

PRECISE = frozenset({GeoPrecision.gps, GeoPrecision.address})
PRECISION_WEIGHT: dict[GeoPrecision, float] = {
    GeoPrecision.gps: 4.0,
    GeoPrecision.address: 3.0,
    GeoPrecision.barrio: 1.0,
    GeoPrecision.none: 0.0,
}
PRECISION_RANK: dict[GeoPrecision, int] = {
    GeoPrecision.gps: 3,
    GeoPrecision.address: 2,
    GeoPrecision.barrio: 1,
    GeoPrecision.none: 0,
}
# Sin ubicación, solo se agrupa por texto casi idéntico (cadenas reenviadas).
NO_GEO_THRESHOLD = 0.5

_ADDRESS_RE = re.compile(
    r"(?<![a-z0-9])(calle|carrera|avenida [a-z]+|diagonal|transversal) (\d{1,3}[a-z]?)(?![0-9])"
)


def address_signature(text: str) -> frozenset[str]:
    """Cruce de vías mencionado ("calle 43 con carrera 23" → {calle 43, carrera 23})."""
    return frozenset(f"{kind} {num}" for kind, num in _ADDRESS_RE.findall(normalize(text)))


def address_relation(report_text: str, candidate_texts: Sequence[str]) -> str:
    """'same' si coincide el cruce, 'different' si todos los cruces conocidos difieren."""
    mine = address_signature(report_text)
    if len(mine) < 2:
        return "unknown"
    theirs = [sig for sig in (address_signature(t) for t in candidate_texts) if len(sig) >= 2]
    if not theirs:
        return "unknown"
    return "same" if any(sig == mine for sig in theirs) else "different"


def compatible_group(category: Category) -> frozenset[Category]:
    for group in COMPATIBLE_GROUPS:
        if category in group:
            return group
    return frozenset({category})


def compatible(a: Category, b: Category) -> bool:
    return b in compatible_group(a)


@dataclass(frozen=True)
class ReportCtx:
    category: Category
    lat: float | None
    lon: float | None
    precision: GeoPrecision
    occurred_at: datetime
    text: str
    reporter_hash: str | None


@dataclass(frozen=True)
class Candidate:
    incident_id: uuid.UUID
    category: Category
    lat: float | None
    lon: float | None
    precision: GeoPrecision
    first_seen: datetime
    last_seen: datetime
    texts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Match:
    incident_id: uuid.UUID
    similarity: float
    distance_m: float | None
    same_address: bool = False

    def rank(self) -> tuple[bool, float, float]:
        """Mismo cruce de vías primero; luego mayor similitud; luego menor distancia."""
        return (self.same_address, self.similarity, -(self.distance_m or 0.0))


def _max_distance(a: GeoPrecision, b: GeoPrecision, cfg: DedupSettings) -> float:
    if a in PRECISE and b in PRECISE:
        return cfg.max_distance_m
    return cfg.max_distance_barrio_m


def _threshold(a: GeoPrecision, b: GeoPrecision, cfg: DedupSettings) -> float:
    if a in PRECISE and b in PRECISE:
        return cfg.similarity_threshold_exact
    return cfg.similarity_threshold


def choose_incident(
    report: ReportCtx,
    candidates: Sequence[Candidate],
    provider: SimilarityProvider,
    cfg: DedupSettings,
) -> Match | None:
    """Incidente al que se une el reporte, o None para crear uno nuevo."""
    window = timedelta(hours=cfg.window_hours)
    best: Match | None = None
    for cand in candidates:
        if not compatible(report.category, cand.category):
            continue
        if not (cand.first_seen - window <= report.occurred_at <= cand.last_seen + window):
            continue
        relation = address_relation(report.text, cand.texts)
        if relation == "different":
            continue
        report_has_point = report.lat is not None and report.lon is not None
        cand_has_point = cand.lat is not None and cand.lon is not None
        distance: float | None = None
        if report_has_point and cand_has_point:
            assert report.lat is not None and report.lon is not None
            assert cand.lat is not None and cand.lon is not None
            distance = haversine_m(report.lat, report.lon, cand.lat, cand.lon)
            if relation == "same":
                # Mismo cruce de vías: la ubicación por barrio o vía es aproximada.
                if distance > cfg.address_match_distance_m:
                    continue
                threshold = 0.0
            elif distance > _max_distance(report.precision, cand.precision, cfg):
                continue
            else:
                threshold = _threshold(report.precision, cand.precision, cfg)
        elif not report_has_point and not cand_has_point:
            threshold = NO_GEO_THRESHOLD
        else:
            continue
        sims = provider.similarities(report.text, cand.texts) if cand.texts else [0.0]
        similarity = min(1.0, max(sims, default=0.0))
        if similarity < threshold:
            continue
        match = Match(cand.incident_id, similarity, distance, relation == "same")
        if best is None or match.rank() > best.rank():
            best = match
    return best


def independent_sources(rows: Iterable[tuple[str | None, Channel, bool]]) -> int:
    """Remitentes distintos que corroboran el hecho.

    - Un remitente que repite no suma (misma huella HMAC).
    - Cada reporte sin remitente identificable cuenta por separado.
    - Los reenvíos de cadena (con señales de desinformación) no son corroboración
      independiente: todos juntos cuentan como una sola fuente.
    """
    hashes: set[str] = set()
    anonymous = 0
    chains = 0
    for reporter_hash, _channel, is_chain in rows:
        if is_chain:
            chains += 1
        elif reporter_hash:
            hashes.add(reporter_hash)
        else:
            anonymous += 1
    independent = len(hashes) + anonymous
    return independent if independent else min(chains, 1)


def weighted_centroid(
    points: Iterable[tuple[float, float, GeoPrecision]],
) -> tuple[float, float] | None:
    total = lat_acc = lon_acc = 0.0
    for lat, lon, precision in points:
        w = PRECISION_WEIGHT[precision] or 0.5
        total += w
        lat_acc += lat * w
        lon_acc += lon * w
    if total == 0:
        return None
    return lat_acc / total, lon_acc / total


# ---------------------------------------------------------------------------- PostGIS


def _point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


async def find_candidates(
    session: AsyncSession, report: ReportCtx, cfg: DedupSettings, limit: int = 20
) -> list[Candidate]:
    window = timedelta(hours=cfg.window_hours)
    group = list(compatible_group(report.category))
    stmt = select(Incident, func.ST_Y(Incident.centroid), func.ST_X(Incident.centroid)).where(
        Incident.category.in_(group),
        Incident.status != IncidentStatus.descartado,
        Incident.last_seen >= report.occurred_at - window,
        Incident.first_seen <= report.occurred_at + window,
    )
    if report.lat is not None and report.lon is not None:
        stmt = stmt.where(
            func.ST_DWithin(
                func.Geography(Incident.centroid),
                func.Geography(func.ST_SetSRID(func.ST_MakePoint(report.lon, report.lat), 4326)),
                max(cfg.max_distance_barrio_m, cfg.address_match_distance_m),
            )
        )
    else:
        stmt = stmt.where(Incident.centroid.is_(None))
    stmt = stmt.order_by(Incident.last_seen.desc()).limit(limit)
    rows: list[Any] = list((await session.execute(stmt)).all())
    if not rows:
        return []

    ids = [inc.id for inc, _, _ in rows]
    text_rows = (
        await session.execute(
            select(Report.incident_id, Report.text_redacted).where(
                and_(Report.incident_id.in_(ids), Report.status != ReportStatus.descartado)
            )
        )
    ).all()
    texts: dict[uuid.UUID, list[str]] = {}
    for incident_id, text in text_rows:
        if incident_id is not None:
            texts.setdefault(incident_id, []).append(text)

    return [
        Candidate(
            incident_id=inc.id,
            category=inc.category,
            lat=lat,
            lon=lon,
            precision=inc.geo_precision,
            first_seen=inc.first_seen,
            last_seen=inc.last_seen,
            texts=texts.get(inc.id, []),
        )
        for inc, lat, lon in rows
    ]


async def recompute_incident(session: AsyncSession, incident: Incident) -> list[Report]:
    """Recalcula agregados del incidente desde sus reportes vigentes (FR-015, FR-016, FR-020)."""
    reports = list(
        (
            await session.execute(
                select(Report).where(
                    Report.incident_id == incident.id, Report.status != ReportStatus.descartado
                )
            )
        ).scalars()
    )
    if not reports:
        incident.report_count = 0
        incident.independent_sources = 0
        return reports

    coords = (
        await session.execute(
            select(Report.id, func.ST_Y(Report.geom), func.ST_X(Report.geom)).where(
                Report.id.in_([r.id for r in reports]), Report.geom.is_not(None)
            )
        )
    ).all()
    by_id = {rid: (lat, lon) for rid, lat, lon in coords}
    points = [(*by_id[r.id], r.geo_precision) for r in reports if r.id in by_id]

    top = max(reports, key=lambda r: (TRIAGE_RANK[r.triage_level], -r.occurred_at.timestamp()))
    best_geo = max(reports, key=lambda r: PRECISION_RANK[r.geo_precision])

    incident.report_count = len(reports)
    incident.independent_sources = independent_sources(
        (r.reporter_hash, r.channel, bool(r.misinfo_signals)) for r in reports
    )
    incident.category = top.category
    incident.triage_level = top.triage_level
    incident.is_life_threat = any(r.is_life_threat for r in reports)
    people = [r.people_affected for r in reports if r.people_affected is not None]
    incident.people_affected = max(people) if people else None
    incident.first_seen = min(r.occurred_at for r in reports)
    incident.last_seen = max(r.occurred_at for r in reports)
    incident.geo_precision = best_geo.geo_precision
    incident.barrio = best_geo.barrio or next((r.barrio for r in reports if r.barrio), None)
    incident.manzana_id = best_geo.manzana_id
    centroid = weighted_centroid(points)
    incident.centroid = _point(*centroid) if centroid else None
    return reports
