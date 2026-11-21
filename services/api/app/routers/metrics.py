"""KPI con fuente y fecha de corte (FR-028 a FR-030, docs/diccionario_indicadores.md).

Los KPI de detección los calcula `scripts/evaluate_kpis.py` contra la verdad del escenario y los
publica aquí como instantáneas; la API nunca lee esa verdad (principio IV).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.db import get_session
from app.domain import DispatchStatus, IncidentStatus, MetricUnit, ReportAction, Role
from app.models import Dispatch, Incident, MetricSnapshot, Report, ReportEvent

router = APIRouter(prefix="/metrics", tags=["métricas"])

INDICATORS: dict[str, tuple[str, str | None]] = {
    "reports_received": ("Reportes recibidos", None),
    "incidents_consolidated": ("Incidentes consolidados", None),
    "duplicate_detection_rate": ("Duplicados detectados", "> 90 %"),
    "fake_detection_rate": ("Falsos detectados", "> 90 %"),
    "false_positive_rate": ("Legítimos marcados como falsos", "lo más bajo posible"),
    "critical_auto_discarded": ("Críticos descartados por la IA", "0"),
    "critical_recall": ("Críticos identificados", "≥ 98 %"),
    "time_to_consolidated_map_min": ("Hecho en el mapa en (p90)", "minutos, no días"),
    "p95_processing_ms": ("Procesamiento por reporte (p95)", "< 1.000 ms"),
    # Despacho (specs/002, research R13): calculados en vivo.
    "critical_without_dispatch": ("Críticos sin despacho", "0"),
    "median_time_to_dispatch_min": ("Tiempo a despacho de críticos (mediana)", "minutos"),
    "double_dispatch_prevented": ("Despachos dobles evitados", None),
}


class SnapshotIn(BaseModel):
    indicator: str = Field(min_length=1, max_length=64)
    value: float
    unit: MetricUnit
    source: str = Field(default="evaluate_kpis.py", max_length=64)
    cutoff_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class SnapshotsIn(BaseModel):
    items: list[SnapshotIn] = Field(min_length=1, max_length=50)


class Kpi(BaseModel):
    indicator: str
    label: str
    value: float | None
    unit: MetricUnit
    source: str
    version: int
    cutoff_at: datetime
    simulated: bool = True
    target: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class KpiList(BaseModel):
    items: list[Kpi]
    cutoff_at: datetime


def _kpi(
    indicator: str,
    value: float | None,
    unit: MetricUnit,
    source: str,
    version: int,
    cutoff: datetime,
    details: dict[str, Any] | None = None,
) -> Kpi:
    label, target = INDICATORS.get(indicator, (indicator, None))
    return Kpi(
        indicator=indicator,
        label=label,
        value=value,
        unit=unit,
        source=source,
        version=version,
        cutoff_at=cutoff,
        target=target,
        details=details or {},
    )


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
async def post_snapshots(
    body: SnapshotsIn,
    _: Role = Depends(require_role(Role.operador_pmu)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    for item in body.items:
        previous = await session.scalar(
            select(func.count()).where(MetricSnapshot.indicator == item.indicator)
        )
        session.add(
            MetricSnapshot(
                indicator=item.indicator,
                value=item.value,
                unit=item.unit,
                source=item.source,
                cutoff_at=item.cutoff_at,
                details=item.details,
                version=(previous or 0) + 1,
            )
        )
    await session.commit()
    bus.publish(
        "kpi.updated",
        {
            "indicators": [i.indicator for i in body.items],
            "cutoff_at": max(i.cutoff_at for i in body.items).isoformat(),
        },
    )
    return {"stored": len(body.items)}


@router.get("/kpi", response_model=KpiList)
async def get_kpi(
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe, Role.publico)),
    session: AsyncSession = Depends(get_session),
) -> KpiList:
    cutoff = datetime.now(UTC)
    reports = await session.scalar(select(func.count()).select_from(Report)) or 0
    incidents = (
        await session.scalar(
            select(func.count()).select_from(Incident).where(Incident.report_count > 0)
        )
        or 0
    )
    p95 = await session.scalar(
        select(func.percentile_cont(0.95).within_group(Report.processing_ms))
    )
    items = [
        _kpi("reports_received", reports, MetricUnit.conteo, "api", reports, cutoff),
        _kpi("incidents_consolidated", incidents, MetricUnit.conteo, "api", reports, cutoff),
        _kpi(
            "p95_processing_ms",
            round(p95) if p95 is not None else None,
            MetricUnit.ms,
            "api",
            reports,
            cutoff,
        ),
        *await _dispatch_kpis(session, cutoff, reports),
    ]

    latest = (
        select(MetricSnapshot.indicator, func.max(MetricSnapshot.version).label("v"))
        .group_by(MetricSnapshot.indicator)
        .subquery()
    )
    snapshots = (
        await session.execute(
            select(MetricSnapshot).join(
                latest,
                (MetricSnapshot.indicator == latest.c.indicator)
                & (MetricSnapshot.version == latest.c.v),
            )
        )
    ).scalars()
    order = list(INDICATORS)
    for snap in sorted(
        snapshots, key=lambda s: order.index(s.indicator) if s.indicator in order else 99
    ):
        items.append(
            _kpi(
                snap.indicator,
                float(snap.value),
                snap.unit,
                snap.source,
                snap.version,
                snap.cutoff_at,
                snap.details,
            )
        )
    return KpiList(items=items, cutoff_at=cutoff)


async def _dispatch_kpis(session: AsyncSession, cutoff: datetime, version: int) -> list[Kpi]:
    """KPI de despacho (specs/002 FR-013): solo incidentes de riesgo vital."""
    live = select(Dispatch.incident_id).where(Dispatch.status != DispatchStatus.cancelado)
    without = await session.scalar(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.is_life_threat.is_(True),
            Incident.report_count > 0,
            Incident.status.in_(
                [IncidentStatus.abierto, IncidentStatus.en_revision, IncidentStatus.verificado]
            ),
            Incident.id.not_in(live),
        )
    )
    # Desde que el incidente se consolidó (hora real), no la hora sintética del evento (R13).
    first = (
        select(
            Dispatch.incident_id,
            func.min(Dispatch.created_at).label("first_at"),
        )
        .where(Dispatch.status != DispatchStatus.cancelado)
        .group_by(Dispatch.incident_id)
        .subquery()
    )
    minutes = func.extract("epoch", first.c.first_at - Incident.created_at) / 60.0
    median = await session.scalar(
        select(func.percentile_cont(0.5).within_group(minutes))
        .select_from(Incident)
        .join(first, first.c.incident_id == Incident.id)
        .where(Incident.is_life_threat.is_(True))
    )
    blocked = await session.scalar(
        select(func.count())
        .select_from(ReportEvent)
        .where(ReportEvent.action == ReportAction.despacho_doble_bloqueado)
    )
    return [
        _kpi("critical_without_dispatch", without or 0, MetricUnit.conteo, "api", version, cutoff),
        _kpi(
            "median_time_to_dispatch_min",
            round(float(median), 1) if median is not None else None,
            MetricUnit.minutes,
            "api",
            version,
            cutoff,
        ),
        _kpi("double_dispatch_prevented", blocked or 0, MetricUnit.conteo, "api", version, cutoff),
    ]
