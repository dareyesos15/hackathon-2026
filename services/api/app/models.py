"""Modelos ORM de la SST (data-model.md). Reportes y bitácora son solo-agregar.

Los índices GIST de las geometrías los crea GeoAlchemy2 (spatial_index=True por defecto).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import (
    Category,
    Channel,
    GeoPrecision,
    IncidentStatus,
    MetricUnit,
    PlaceKind,
    ReportAction,
    ReportStatus,
    Role,
    TriageLevel,
    TrustLabel,
)


def _enum(cls: type[StrEnum], name: str) -> SAEnum:
    """VARCHAR + CHECK (sin tipos ENUM nativos: migraciones más simples)."""
    return SAEnum(
        cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    pass


class CommonMixin:
    """Columnas comunes de trazabilidad (principio V)."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="SIMULADO")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Manzana(Base):
    __tablename__ = "manzanas"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # MZ-####
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="SIMULADO")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    geom: Mapped[Any] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    barrio: Mapped[str] = mapped_column(String(80), nullable=False)
    comuna: Mapped[str] = mapped_column(String(80), nullable=False)
    seismic_zone: Mapped[str] = mapped_column(String(32), nullable=False)
    population: Mapped[int] = mapped_column(Integer, nullable=False)
    buildings_pre_1984_pct: Mapped[float] = mapped_column(Float, nullable=False)


class Place(CommonMixin, Base):
    __tablename__ = "places"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    kind: Mapped[PlaceKind] = mapped_column(_enum(PlaceKind, "place_kind"), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    barrio: Mapped[str] = mapped_column(String(80), nullable=False)


class Incident(CommonMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("trust_score BETWEEN 0 AND 100", name="ck_incident_trust_range"),
        Index("ix_incidents_category_last_seen", "category", "last_seen"),
    )

    centroid: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    category: Mapped[Category] = mapped_column(_enum(Category, "category"), nullable=False)
    triage_level: Mapped[TriageLevel] = mapped_column(
        _enum(TriageLevel, "triage_level"), nullable=False
    )
    is_life_threat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    independent_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    people_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trust_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    trust_label: Mapped[TrustLabel] = mapped_column(
        _enum(TrustLabel, "trust_label"), nullable=False, default=TrustLabel.posible_falso
    )
    trust_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        _enum(IncidentStatus, "incident_status"), nullable=False, default=IncidentStatus.abierto
    )
    manzana_id: Mapped[str | None] = mapped_column(ForeignKey("manzanas.id"), nullable=True)
    barrio: Mapped[str | None] = mapped_column(String(80), nullable=True)
    geo_precision: Mapped[GeoPrecision] = mapped_column(
        _enum(GeoPrecision, "geo_precision"), nullable=False, default=GeoPrecision.none
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Report(CommonMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_report_severity"),
        CheckConstraint("people_affected IS NULL OR people_affected >= 0", name="ck_report_people"),
        CheckConstraint("char_length(text_redacted) <= 2000", name="ck_report_text_len"),
        CheckConstraint(
            "(geo_precision = 'none') OR (geom IS NOT NULL)", name="ck_report_geom_precision"
        ),
        Index("ix_reports_category_occurred", "category", "occurred_at"),
        Index("ix_reports_incident", "incident_id"),
    )

    client_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    channel: Mapped[Channel] = mapped_column(_enum(Channel, "channel"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    text_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    geo_precision: Mapped[GeoPrecision] = mapped_column(
        _enum(GeoPrecision, "geo_precision"), nullable=False
    )
    manzana_id: Mapped[str | None] = mapped_column(ForeignKey("manzanas.id"), nullable=True)
    barrio: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[Category] = mapped_column(_enum(Category, "category"), nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    triage_level: Mapped[TriageLevel] = mapped_column(
        _enum(TriageLevel, "triage_level"), nullable=False
    )
    is_life_threat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    people_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    misinfo_signals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        _enum(ReportStatus, "report_status"), nullable=False, default=ReportStatus.nuevo
    )
    processing_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReportEvent(CommonMixin, Base):
    __tablename__ = "report_events"
    __table_args__ = (
        CheckConstraint("report_id IS NOT NULL OR incident_id IS NOT NULL", name="ck_event_target"),
        Index("ix_report_events_report", "report_id"),
        Index("ix_report_events_incident", "incident_id"),
    )

    report_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("reports.id"), nullable=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    actor_role: Mapped[Role] = mapped_column(_enum(Role, "actor_role"), nullable=False)
    action: Mapped[ReportAction] = mapped_column(
        _enum(ReportAction, "report_action"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MetricSnapshot(CommonMixin, Base):
    __tablename__ = "metrics_snapshots"
    __table_args__ = (Index("ix_metrics_indicator_cutoff", "indicator", "cutoff_at"),)

    indicator: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[MetricUnit] = mapped_column(_enum(MetricUnit, "metric_unit"), nullable=False)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
