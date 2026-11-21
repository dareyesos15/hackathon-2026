"""Esquemas de la alerta masiva de toda la ciudad."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain import AlertChannel, Category, MassAlertEvent, MassAlertStatus, Role, TriageLevel


class MassAlertIn(BaseModel):
    title: str = Field(min_length=1, max_length=120, examples=["Sismo M 6,1 · Manizales"])
    event_type: MassAlertEvent
    description: str | None = Field(default=None, max_length=1000)
    official_alert: bool = Field(
        default=True,
        description="Crear también el borrador de alerta oficial para toda la ciudad "
        "(la aprueba el COE, EMRE tarea 5.5)",
    )
    message: str | None = Field(
        default=None,
        max_length=160,
        description="Mensaje de la alerta oficial; si falta se genera uno estándar",
    )
    channels: list[AlertChannel] = Field(
        default_factory=lambda: [AlertChannel.tablero, AlertChannel.mapa_publico]
    )


class MassAlertOut(BaseModel):
    id: uuid.UUID
    title: str
    event_type: MassAlertEvent
    description: str | None
    status: MassAlertStatus
    started_at: datetime
    resolved_at: datetime | None
    created_by_role: Role
    official_alert_id: uuid.UUID | None
    incidents_total: int
    incidents_closed: int
    has_report: bool


class MassAlertList(BaseModel):
    items: list[MassAlertOut]
    active: list[MassAlertOut]
    unassigned_count: int = Field(description="Incidentes que esperan asignación manual")


class MassAlertCloseIn(BaseModel):
    delete_incidents: bool = Field(
        default=False,
        description="Cerrar aunque queden abiertos, eliminando todos los incidentes asociados",
    )


class MassAlertCloseOut(BaseModel):
    mass_alert: MassAlertOut
    deleted_incidents: int


class IncidentAssignIn(BaseModel):
    incident_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    mass_alert_id: uuid.UUID | None = Field(
        default=None, description="Alerta masiva activa destino; null = operación ordinaria"
    )


class ManualIncidentIn(BaseModel):
    category: Category
    description: str = Field(min_length=3, max_length=1000)
    triage_level: TriageLevel | None = Field(
        default=None, description="Si falta, el de la categoría (matriz de triaje)"
    )
    barrio: str | None = Field(default=None, max_length=80)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    people_affected: int | None = Field(default=None, ge=0, le=10000)
    mass_alert_id: uuid.UUID | None = Field(
        default=None, description="Alerta masiva activa; null = operación ordinaria"
    )


class MassAlertReport(BaseModel):
    """Reporte de problemas, trazabilidad y tiempos (preliminar mientras la alerta siga activa)."""

    mass_alert: MassAlertOut
    report: dict[str, Any]
