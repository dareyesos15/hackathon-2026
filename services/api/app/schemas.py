"""Esquemas Pydantic del contrato REST /api/v1 (contracts/rest-api.md). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import (
    Category,
    Channel,
    DispatchStatus,
    EmreFunction,
    GeoPrecision,
    IncidentStatus,
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


class IncidentDetail(IncidentSummary):
    trust_breakdown: dict[str, Any]
    reports: list[ReportOut]
    events: list[ReportEventOut]
    dispatches: list[DispatchOut] = Field(default_factory=list)
    suggestion: DispatchSuggestion | None = None


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
