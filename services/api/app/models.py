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
    MassAlertEvent,
    MassAlertStatus,
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
    ZoneDetector,
    ZoneEventKind,
    ZoneSensorStatus,
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


class MassAlert(CommonMixin, Base):
    """Alerta masiva de toda la ciudad (p. ej. un sismo): sesión de operación propia.

    Puede haber varias activas a la vez. Mientras exista al menos una, los incidentes nuevos
    quedan *sin asignar* y el PMU/COE los asigna a mano. El cierre es manual y guarda el reporte
    final (problemas, trazabilidad y tiempos de solución) en `final_report`.
    """

    __tablename__ = "mass_alerts"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_mass_alert_title_len"),
        CheckConstraint(
            "created_by_role IN ('operador_pmu', 'coe')", name="ck_mass_alert_created_by_role"
        ),
        Index("ix_mass_alerts_status", "status"),
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[MassAlertEvent] = mapped_column(
        _enum(MassAlertEvent, "mass_alert_event"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MassAlertStatus] = mapped_column(
        _enum(MassAlertStatus, "mass_alert_status"), nullable=False, default=MassAlertStatus.activa
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_role: Mapped[Role] = mapped_column(
        _enum(Role, "mass_alert_created_by"), nullable=False
    )
    official_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )
    final_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Incident(CommonMixin, Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("trust_score BETWEEN 0 AND 100", name="ck_incident_trust_range"),
        Index("ix_incidents_category_last_seen", "category", "last_seen"),
        Index("ix_incidents_mass_alert", "mass_alert_id"),
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
    # Sesión de alerta masiva a la que pertenece (None: operación ordinaria).
    mass_alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mass_alerts.id"), nullable=True
    )
    # Creado mientras había alertas masivas activas: espera que el PMU/COE lo asigne.
    pending_assignment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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
    # Campos del RUD (UNGRD). Solo conteos: nada identifica a una persona (Ley 1581).
    census_form_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    tenure: Mapped[str | None] = mapped_column(String(16), nullable=True)
    housing_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age_0_5: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    age_6_17: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    age_18_59: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    age_60_plus: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    female_members: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    ethnic_members: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    losses: Mapped[list[str]] = mapped_column(ARRAY(String(24)), nullable=False, default=list)


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


class PropertyReview(CommonMixin, Base):
    """Revisión a predio (formato GUE-RPD-FR-02 v4). Una por formulario; liga la evaluación de
    habitabilidad y el hogar del censo. Ley 1581: sin nombres, teléfonos, cédulas ni fechas de
    nacimiento; el propietario (si el encuestado es arrendatario) solo como HMAC con sal.
    """

    __tablename__ = "property_reviews"
    __table_args__ = (Index("ix_property_reviews_property", "property_id", "reviewed_at"),)

    form_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("building_inspections.id"), nullable=False, unique=True
    )
    property_id: Mapped[str] = mapped_column(String(160), nullable=False)
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("households.id"), nullable=True
    )
    respondent_relation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    owner_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    residents: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    event_status: Mapped[str] = mapped_column(String(16), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(ARRAY(String(24)), nullable=False)
    event_other: Mapped[str | None] = mapped_column(Text, nullable=True)
    structural_causes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    affectation: Mapped[str] = mapped_column(String(16), nullable=False)
    affected_areas_m2: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False, default=dict)
    belongings_loss: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrals: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False, default=list)
    referral_other: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrals_done: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list
    )
    evacuation_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewer_agency: Mapped[str] = mapped_column(String(80), nullable=False)
    notified_signed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recorded_by_role: Mapped[str] = mapped_column(String(32), nullable=False)


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
    # Acta de entrega de ayuda humanitaria.
    act_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    delivered_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    amount_cop: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    months: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    shelter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shelters.id"), nullable=True)
    signed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="abierto")
    services: Mapped[list[str]] = mapped_column(ARRAY(String(24)), nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ------------------------------------------- sensor de zonas inseguras (specs/004, NC2025/0015763)


class ZoneSensor(CommonMixin, Base):
    """Dispositivo de monitoreo de zonas inseguras instalado en un sitio acordonado."""

    __tablename__ = "zone_sensors"

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    heading_deg: Mapped[float] = mapped_column(Float, nullable=False)
    range_m: Mapped[float] = mapped_column(Float, nullable=False)
    half_angle_deg: Mapped[float] = mapped_column(Float, nullable=False)
    # Sin llave foránea: el reinicio de la demo trunca incidentes y debe conservar los sensores.
    incident_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[ZoneSensorStatus] = mapped_column(
        _enum(ZoneSensorStatus, "zone_sensor_status"),
        nullable=False,
        default=ZoneSensorStatus.armado,
    )
    battery_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RfidBadge(CommonMixin, Base):
    """Credencial RFID de personal autorizado (módulo 300). Código institucional, no personal."""

    __tablename__ = "rfid_badges"

    tag: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    agency_code: Mapped[str] = mapped_column(String(32), nullable=False)
    role_label: Mapped[str] = mapped_column(String(80), nullable=False)


class ZoneSensorEvent(CommonMixin, Base):
    """Evento del sensor. Solo-agregar salvo la atención (quién y cuándo)."""

    __tablename__ = "zone_sensor_events"
    __table_args__ = (Index("ix_zone_sensor_events_at", "at"),)

    sensor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("zone_sensors.id"), nullable=False)
    kind: Mapped[ZoneEventKind] = mapped_column(
        _enum(ZoneEventKind, "zone_event_kind"), nullable=False
    )
    detector: Mapped[ZoneDetector | None] = mapped_column(
        _enum(ZoneDetector, "zone_detector"), nullable=True
    )
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    bearing_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    rfid_tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    authorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    battery_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
