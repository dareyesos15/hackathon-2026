"""Esquemas Pydantic del contrato REST /api/v1 (contracts/rest-api.md). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain import (
    Category,
    Channel,
    GeoPrecision,
    IncidentStatus,
    ReportAction,
    ReportStatus,
    Role,
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
    action: Literal["confirmar", "descartar", "marcar_duplicado", "reabrir"]
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


class ReportEventOut(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    actor_role: Role
    action: ReportAction
    payload: dict[str, Any]
    at: datetime


class IncidentDetail(IncidentSummary):
    trust_breakdown: dict[str, Any]
    reports: list[ReportOut]
    events: list[ReportEventOut]


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
