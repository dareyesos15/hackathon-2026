"""Esquemas Pydantic del contrato REST /api/v1 (contracts/rest-api.md). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain import (
    AlertAction,
    AlertChannel,
    AlertStatus,
    AlertType,
    CascadeLevel,
    Category,
    Channel,
    DispatchStatus,
    EmreFunction,
    GeoPrecision,
    IncidentStatus,
    RecipientRole,
    ReportAction,
    ReportStatus,
    ResourceStatus,
    ResourceType,
    Role,
    TrackKind,
    TrackOrigin,
    TriageLevel,
    TrustLabel,
)

# ---------------------------------------------------------------------------- entrada


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    precision: Literal["gps", "address"] = "gps"


class ReportIn(BaseModel):
    """Reporte de la app ciudadana o de una entidad (Report.client_uuid, Report.channel)."""

    client_uuid: uuid.UUID
    channel: Channel = Channel.pwa
    occurred_at: datetime | None = None
    text: str = Field(min_length=1, max_length=2000)
    category_hint: Category | None = None
    location: LocationIn | None = None
    barrio: str | None = Field(default=None, max_length=80)
    people_affected: int | None = Field(default=None, ge=0, le=100_000)
    has_media: bool = False
    reporter_contact: str | None = Field(
        default=None, max_length=120, description="Se hashea y nunca se guarda ni se devuelve"
    )
    consent: bool = False


class SmsIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from", min_length=3, max_length=32)
    body: str = Field(min_length=1, max_length=1000)
    received_at: datetime | None = None


class BatchIn(BaseModel):
    items: list[ReportIn] = Field(min_length=1, max_length=50)


class ReviewIn(BaseModel):
    action: Literal["confirmar", "descartar", "marcar_duplicado", "reabrir", "cerrar_atendido"]
    duplicate_of_incident: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------- salida


class ReportOut(BaseModel):
    id: uuid.UUID
    client_uuid: uuid.UUID
    channel: Channel
    received_at: datetime
    occurred_at: datetime
    text_redacted: str
    location_text: str | None
    lat: float | None
    lon: float | None
    geo_precision: GeoPrecision
    manzana_id: str | None
    barrio: str | None
    category: Category
    severity: int
    triage_level: TriageLevel
    is_life_threat: bool
    people_affected: int | None
    has_media: bool
    misinfo_signals: list[str]
    incident_id: uuid.UUID | None
    status: ReportStatus
    processing_ms: int
    source: str
    version: int


class IncidentSummary(BaseModel):
    id: uuid.UUID
    lat: float | None
    lon: float | None
    category: Category
    triage_level: TriageLevel
    is_life_threat: bool
    report_count: int
    independent_sources: int
    people_affected: int | None
    trust_score: int
    trust_label: TrustLabel
    status: IncidentStatus
    first_seen: datetime
    last_seen: datetime
    manzana_id: str | None
    barrio: str | None
    geo_precision: GeoPrecision
    updated_at: datetime
    source: str
    mass_alert_id: uuid.UUID | None = Field(
        default=None, description="Sesión de alerta masiva (None: operación ordinaria)"
    )
    pending_assignment: bool = Field(
        default=False, description="Sin asignar: espera que el PMU/COE elija su sesión"
    )
    # Despacho (specs/002): derivados del despacho más reciente no cancelado.
    dispatch_status: Literal["sin_despacho", "en_camino", "en_sitio", "finalizado"] = "sin_despacho"
    assigned_agency: str | None = None
    unattended: bool = Field(
        default=False, description="Riesgo vital sin despacho por más del umbral configurado"
    )


class ReportEventOut(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    actor_role: Role
    action: ReportAction
    payload: dict[str, Any]
    at: datetime


# ---------------------------------------------------------------- despacho (specs/002 US1)


class AgencyRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class AgencyOut(AgencyRef):
    emre_function: EmreFunction
    resources_available: int
    resources_total: int


class AgencyList(BaseModel):
    items: list[AgencyOut]


class ResourceOut(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    type: ResourceType
    status: ResourceStatus
    agency_id: uuid.UUID
    agency_code: str
    lat: float
    lon: float
    last_seen_at: datetime | None
    active_dispatch_id: uuid.UUID | None
    source: str


class ResourceList(BaseModel):
    items: list[ResourceOut]
    cutoff_at: datetime


class TrackIn(BaseModel):
    kind: TrackKind
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    at: datetime | None = Field(default=None, description="Hora del paso; por defecto, ahora")


class TrackOut(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    dispatch_id: uuid.UUID | None
    kind: TrackKind
    origin: TrackOrigin
    lat: float
    lon: float
    at: datetime
    source: str


class TrackList(BaseModel):
    items: list[TrackOut]


class DispatchIn(BaseModel):
    """Despacho idempotente por `client_uuid` (data-model.md Dispatch.client_uuid)."""

    client_uuid: uuid.UUID
    incident_id: uuid.UUID
    resource_ids: list[uuid.UUID] = Field(max_length=5)
    is_reinforcement: bool = False
    justification: str | None = Field(default=None, max_length=500)


class DispatchPatchIn(BaseModel):
    action: Literal["llegada", "finalizar", "cancelar", "fuera_de_servicio"]
    note: str | None = Field(default=None, max_length=500)


class DispatchOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    resource: ResourceOut
    agency: AgencyRef
    emre_function: EmreFunction | None
    suggested: bool
    is_reinforcement: bool
    justification: str | None
    status: DispatchStatus
    eta_at: datetime
    distance_m: int
    created_by_role: Role
    created_at: datetime
    arrived_at: datetime | None
    closed_at: datetime | None
    close_note: str | None
    source: str


class DispatchList(BaseModel):
    items: list[DispatchOut]
    cutoff_at: datetime


class CandidateOut(BaseModel):
    resource: ResourceOut
    agency_code: str
    distance_m: int
    eta_min: float
    source: str = "SIMULADO"


class DispatchSuggestion(BaseModel):
    emre_function: EmreFunction | None
    emre_function_label: str | None
    suggested_agency: AgencyRef | None
    alternative_agencies: list[AgencyRef]
    candidates: list[CandidateOut]
    fallback_used: bool


class RecipientOut(BaseModel):
    """Actor que debe recibir la información del incidente (EMRE, anexos I–VI)."""

    agency: AgencyRef
    role: RecipientRole
    emre_function: EmreFunction
    emre_function_label: str
    emre_task: str
    reason: str
    dispatched: bool = Field(description="La agencia ya tiene un despacho activo en el incidente")


class PlanLineOut(BaseModel):
    agency: AgencyRef
    role: RecipientRole
    emre_task: str
    candidate: CandidateOut | None = Field(
        description="Recurso más cercano propuesto; null si no hay o si la agencia ya fue"
    )
    already_dispatched: bool


class IncidentRouting(BaseModel):
    """A quién le llega el incidente y plan de despacho multiagencia propuesto (SIMULADO)."""

    recipients: list[RecipientOut]
    notify_coe: bool
    coe_reason: str | None
    held: bool = Field(description="Aviso retenido: posible falso sin riesgo vital")
    hold_reason: str | None
    notes: list[str]
    plan: list[PlanLineOut]
    plan_resource_ids: list[uuid.UUID]


class DispatchPlanIn(BaseModel):
    """Confirma el plan multiagencia; `resource_ids` permite despachar solo parte de él."""

    client_uuid: uuid.UUID
    resource_ids: list[uuid.UUID] | None = Field(default=None, max_length=8)


class InboxItem(BaseModel):
    incident: IncidentSummary
    role: RecipientRole
    emre_task: str
    reason: str
    dispatched: bool = Field(description="La agencia ya tiene un recurso en camino o en sitio")
    notify_coe: bool


class InboxList(BaseModel):
    agency: AgencyRef
    items: list[InboxItem]
    cutoff_at: datetime


class IncidentDetail(IncidentSummary):
    trust_breakdown: dict[str, Any]
    reports: list[ReportOut]
    events: list[ReportEventOut]
    dispatches: list[DispatchOut] = Field(default_factory=list)
    suggestion: DispatchSuggestion | None = None
    routing: IncidentRouting | None = None


class ReportResult(BaseModel):
    report: ReportOut
    incident: IncidentSummary
    joined_existing_incident: bool
    created: bool
    processing_ms: int


class BatchItemResult(BaseModel):
    client_uuid: uuid.UUID
    status: Literal["created", "duplicate", "error"]
    report_id: uuid.UUID | None = None
    error: str | None = None


class BatchOut(BaseModel):
    results: list[BatchItemResult]


class ReportList(BaseModel):
    items: list[ReportOut]
    next_cursor: str | None
    cutoff_at: datetime


class IncidentList(BaseModel):
    items: list[IncidentSummary]
    cutoff_at: datetime


class ReviewOut(BaseModel):
    report: ReportOut | None
    incident: IncidentSummary
    events: list[ReportEventOut]


# ------------------------------------------------------------------ alertas (specs/002 US2)


class CircleIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(ge=100, le=3000)


class AlertAreaIn(BaseModel):
    """Uno o más barrios, o un círculo marcado en el mapa (research R8)."""

    barrios: list[str] | None = Field(default=None, max_length=30)
    circle: CircleIn | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> AlertAreaIn:
        if bool(self.barrios) == bool(self.circle):
            raise ValueError("Defina el área con barrios o con un círculo (uno de los dos)")
        return self


class AlertIn(BaseModel):
    type: AlertType
    area: AlertAreaIn
    message: str = Field(min_length=1, max_length=500)
    channels: list[AlertChannel] = Field(min_length=1, max_length=3)
    origin_incident_id: uuid.UUID | None = None
    origin_manzana_id: str | None = Field(default=None, max_length=16)
    confirm_misinformation: bool = False


class AlertPatchIn(BaseModel):
    version: int = Field(ge=1)
    type: AlertType | None = None
    area: AlertAreaIn | None = None
    message: str | None = Field(default=None, min_length=1, max_length=500)
    channels: list[AlertChannel] | None = Field(default=None, min_length=1, max_length=3)
    confirm_misinformation: bool = False


class AlertDecisionIn(BaseModel):
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class AlertCancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DeliveryOut(BaseModel):
    channel: AlertChannel
    recipients_count: int | None
    at: datetime
    source: str


class AlertOut(BaseModel):
    id: uuid.UUID
    type: AlertType
    status: AlertStatus
    version: int
    area: dict[str, Any] = Field(description="GeoJSON MultiPolygon")
    area_barrios: list[str]
    area_circle: dict[str, float] | None
    message: str
    channels: list[AlertChannel]
    misinfo_signals: list[str]
    origin_incident_id: uuid.UUID | None
    origin_manzana_id: str | None
    created_by_role: Role
    approved_by_role: Role | None
    created_at: datetime
    updated_at: datetime
    emitted_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    deliveries: list[DeliveryOut]
    source: str


class AlertList(BaseModel):
    items: list[AlertOut]
    cutoff_at: datetime


class AlertEventOut(BaseModel):
    id: uuid.UUID
    action: AlertAction
    actor_role: Role
    alert_version: int
    payload: dict[str, Any]
    at: datetime


class AlertEventList(BaseModel):
    items: list[AlertEventOut]


# ------------------------------------------------------------------ cascada (specs/002 US3)


class RainIn(BaseModel):
    mm_3h: float = Field(ge=0, le=300)
    station_code: str = Field(default="LLUVIA-URB-01", max_length=32)


class RainOut(BaseModel):
    id: uuid.UUID
    station_code: str
    mm_3h: float
    at: datetime
    source: str


class RainSourceIn(BaseModel):
    source: Literal["simulado", "cdiac"]


class RainStationOut(BaseModel):
    code: str
    name: str
    mm_3h: float
    last_data_at: datetime


class RainSourceStatus(BaseModel):
    """Fuente de lluvia de la cascada y estado del sondeo a CDIAC/SIMAC."""

    source: Literal["simulado", "cdiac"]
    effective: Literal["simulado", "cdiac", "cdiac_respaldo"]
    poll_interval_s: float
    max_age_min: float
    last_attempt_at: datetime | None
    last_ok_at: datetime | None
    last_error: str | None
    stations: list[RainStationOut]
    catalog_size: int
    attribution: str


class CascadeFactor(BaseModel):
    puntos: float
    max: float
    detalle: str


class CascadeProperties(BaseModel):
    """Propiedades de cada manzana en `GET /map/cascade` (data-model.md §Estimación de cascada)."""

    manzana_id: str
    barrio: str
    level: CascadeLevel
    score: float
    slope_deg: float
    breakdown: dict[str, CascadeFactor]
    model_version: str
    source: str = "SIMULADO"
