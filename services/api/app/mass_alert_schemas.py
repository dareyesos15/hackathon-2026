"""Esquemas de la alerta masiva de toda la ciudad."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain import AlertChannel, MassAlertEvent, MassAlertStatus, Role


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
    active: MassAlertOut | None


class MassAlertReport(BaseModel):
    """Reporte de problemas, trazabilidad y tiempos (preliminar mientras la alerta siga activa)."""

    mass_alert: MassAlertOut
    report: dict[str, Any]
