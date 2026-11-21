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
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import (
    AidType,
    AlertAction,
    AlertStatus,
    AlertType,
    Category,
    Channel,
    DamageLevel,
    DispatchStatus,
    EmreFunction,
    GeoPrecision,
    IncidentStatus,
    InspectionColor,
    MetricUnit,
    PlaceKind,
    ReportAction,
    ReportStatus,
    ResourceStatus,
    ResourceType,
    Role,
    RudStatus,
    TrackKind,
    TrackOrigin,
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


# --- Despacho, alertas y cascada (specs/002-dispatch-alerts-prediction/data-model.md) ---


class Agency(CommonMixin, Base):
    """Organismo de respuesta del catálogo SIMULADO (data/seed/resources.json)."""

    __tablename__ = "agencies"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    emre_function: Mapped[EmreFunction] = mapped_column(
        _enum(EmreFunction, "emre_function"), nullable=False
    )


class Resource(CommonMixin, Base):
    """Cuadrilla o vehículo; `code` es la etiqueta RFID (SIMULADA) estable."""

    __tablename__ = "resources"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id"), nullable=False)
    type: Mapped[ResourceType] = mapped_column(_enum(ResourceType, "resource_type"), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    base_geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    status: Mapped[ResourceStatus] = mapped_column(
        _enum(ResourceStatus, "resource_status"), nullable=False, default=ResourceStatus.disponible
    )
    last_geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Dispatch(CommonMixin, Base):
    """Asignación de un recurso a un incidente. Nunca se borra (principio III)."""

    __tablename__ = "dispatches"
    __table_args__ = (
        CheckConstraint(
            "NOT is_reinforcement OR char_length(btrim(coalesce(justification, ''))) > 0",
            name="ck_dispatch_reinforcement_justified",
        ),
        CheckConstraint(
            "char_length(coalesce(justification, '')) <= 500", name="ck_dispatch_justification_len"
        ),
        CheckConstraint(
            "char_length(coalesce(close_note, '')) <= 500", name="ck_dispatch_close_note_len"
        ),
        CheckConstraint(
            "created_by_role IN ('operador_pmu', 'coe')", name="ck_dispatch_created_by_role"
        ),
        # Un recurso solo puede tener un despacho activo (FR-005).
        Index(
            "uq_dispatch_active_resource",
            "resource_id",
            unique=True,
            postgresql_where=text("status IN ('en_camino', 'en_sitio')"),
        ),
        Index("ix_dispatches_incident", "incident_id"),
    )

    client_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id"), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), nullable=False)
    agency_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agencies.id"), nullable=False)
    emre_function: Mapped[EmreFunction | None] = mapped_column(
        _enum(EmreFunction, "dispatch_emre_function"), nullable=True
    )
    suggested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_reinforcement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DispatchStatus] = mapped_column(
        _enum(DispatchStatus, "dispatch_status"), nullable=False, default=DispatchStatus.en_camino
    )
    eta_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_role: Mapped[Role] = mapped_column(
        _enum(Role, "dispatch_created_by"), nullable=False
    )
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResourceTrack(CommonMixin, Base):
    """Punto de paso (lector RFID SIMULADO o registro manual). Solo-agregar."""

    __tablename__ = "resource_tracks"
    __table_args__ = (Index("ix_resource_tracks_resource_at", "resource_id", "at"),)

    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id"), nullable=False)
    dispatch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dispatches.id"), nullable=True
    )
    kind: Mapped[TrackKind] = mapped_column(_enum(TrackKind, "track_kind"), nullable=False)
    origin: Mapped[TrackOrigin] = mapped_column(_enum(TrackOrigin, "track_origin"), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


ALERT_CHANNELS_SQL = "ARRAY['tablero', 'mapa_publico', 'sms_cuadrillas']::text[]"


class Alert(CommonMixin, Base):
    """Alerta oficial: solo el COE la aprueba (EMRE tarea 5.5, principio III)."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "approved_by_role IS NULL OR approved_by_role = 'coe'", name="ck_alert_approved_by_coe"
        ),
        CheckConstraint("char_length(message) BETWEEN 1 AND 500", name="ck_alert_message_len"),
        CheckConstraint(
            f"cardinality(channels) >= 1 AND channels <@ {ALERT_CHANNELS_SQL}",
            name="ck_alert_channels",
        ),
        CheckConstraint(
            "char_length(coalesce(close_reason, '')) <= 500", name="ck_alert_close_reason_len"
        ),
        CheckConstraint(
            "created_by_role IN ('operador_pmu', 'coe')", name="ck_alert_created_by_role"
        ),
        Index("ix_alerts_status", "status"),
    )

    type: Mapped[AlertType] = mapped_column(_enum(AlertType, "alert_type"), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        _enum(AlertStatus, "alert_status"), nullable=False, default=AlertStatus.borrador
    )
    area: Mapped[Any] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    area_barrios: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    area_circle: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    misinfo_signals: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    origin_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True
    )
    origin_manzana_id: Mapped[str | None] = mapped_column(ForeignKey("manzanas.id"), nullable=True)
    created_by_role: Mapped[Role] = mapped_column(_enum(Role, "alert_created_by"), nullable=False)
    approved_by_role: Mapped[Role | None] = mapped_column(
        _enum(Role, "alert_approved_by"), nullable=True
    )
    emitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AlertEvent(CommonMixin, Base):
    """Bitácora de alertas (solo-agregar)."""

    __tablename__ = "alert_events"
    __table_args__ = (Index("ix_alert_events_alert", "alert_id", "at"),)

    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), nullable=False)
    actor_role: Mapped[Role] = mapped_column(_enum(Role, "alert_actor_role"), nullable=False)
    action: Mapped[AlertAction] = mapped_column(_enum(AlertAction, "alert_action"), nullable=False)
    alert_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlertDelivery(CommonMixin, Base):
    """Envío SIMULADO por canal. Solo conteos: nunca números ni identidades (principio I)."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (
        CheckConstraint(
            "recipients_count IS NULL OR recipients_count >= 0", name="ck_delivery_recipients"
        ),
        CheckConstraint(
            "channel IN ('tablero', 'mapa_publico', 'sms_cuadrillas')", name="ck_delivery_channel"
        ),
    )

    alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alerts.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipients_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RainReading(CommonMixin, Base):
    """Lluvia acumulada en 3 h de una estación SIMULADA (patente NC2022/0005821)."""

    __tablename__ = "rain_readings"
    __table_args__ = (
        CheckConstraint("mm_3h >= 0 AND mm_3h <= 300", name="ck_rain_range"),
        Index("ix_rain_readings_at", "at"),
    )

    station_code: Mapped[str] = mapped_column(String(32), nullable=False)
    mm_3h: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------- recuperación (specs/003)


class BuildingInspection(CommonMixin, Base):
    """Evaluación de habitabilidad (semáforo). Solo-agregar: el estado vigente es la última."""

    __tablename__ = "building_inspections"
    __table_args__ = (Index("ix_building_inspections_property", "property_id", "at"),)

    property_id: Mapped[str] = mapped_column(String(160), nullable=False)
    manzana_id: Mapped[str | None] = mapped_column(ForeignKey("manzanas.id"), nullable=True)
    color: Mapped[InspectionColor] = mapped_column(
        _enum(InspectionColor, "inspection_color"), nullable=False
    )
    damage_level: Mapped[DamageLevel] = mapped_column(
        _enum(DamageLevel, "damage_level"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspector_role: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Household(CommonMixin, Base):
    """Hogar del censo único. Solo el hash con sal del documento del jefe de hogar."""

    __tablename__ = "households"

    household_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    members_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    property_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    manzana_id: Mapped[str | None] = mapped_column(ForeignKey("manzanas.id"), nullable=True)
    rud_status: Mapped[RudStatus] = mapped_column(
        _enum(RudStatus, "rud_status"), nullable=False, default=RudStatus.pendiente
    )
    pets_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class HouseholdVulnerability(Base):
    """Datos sensibles (Ley 1581): tabla separada, acceso solo PMU/COE."""

    __tablename__ = "household_vulnerability"

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    children: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    elderly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disability: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pregnancy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AidDelivery(CommonMixin, Base):
    """Ayuda entregada a un hogar. `is_duplicate` marca entregas repetidas justificadas."""

    __tablename__ = "aid_deliveries"
    __table_args__ = (Index("ix_aid_deliveries_household", "household_id", "aid_type", "at"),)

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    aid_type: Mapped[AidType] = mapped_column(_enum(AidType, "aid_type"), nullable=False)
    source_fund: Mapped[str] = mapped_column(String(80), nullable=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Shelter(CommonMixin, Base):
    """Albergue temporal (SIMULADO)."""

    __tablename__ = "shelters"
    __table_args__ = (
        CheckConstraint("people >= 0 AND people <= capacity", name="ck_shelter_capacity"),
        CheckConstraint("pets >= 0", name="ck_shelter_pets"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    barrio: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
