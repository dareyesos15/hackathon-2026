"""Esquemas del sensor de zonas inseguras (specs/004, patente NC2025/0015763)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain import ZoneDetector, ZoneEventKind, ZoneSensorStatus


class ZoneSensorIn(BaseModel):
    """Instalación de un sensor: en un incidente (usa su ubicación) o en un punto."""

    label: str = Field(min_length=3, max_length=120)
    incident_id: uuid.UUID | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    heading_deg: float = Field(default=0, ge=0, lt=360)
    range_m: float = Field(default=12, gt=0, le=40)
    half_angle_deg: float = Field(default=30, gt=0, le=90)


class ZoneReadingIn(BaseModel):
    """Lectura cruda del dispositivo (punto de integración con el hardware real)."""

    ultrasonic_m: float | None = Field(default=None, ge=0, le=100)
    infrared: bool = False
    bearing_deg: float = Field(default=0, ge=-180, le=180)
    rfid_tag: str | None = Field(default=None, max_length=32)
    battery_pct: int = Field(default=100, ge=0, le=100)
    tamper: bool = False


class ZoneEventOut(BaseModel):
    id: uuid.UUID
    sensor_id: uuid.UUID
    sensor_code: str
    sensor_label: str
    kind: ZoneEventKind
    detector: ZoneDetector | None
    distance_m: float | None
    bearing_deg: float | None
    rfid_tag: str | None
    badge_agency: str | None
    authorized: bool
    battery_pct: int | None
    at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    source: str


class ZoneEventList(BaseModel):
    items: list[ZoneEventOut]
    cutoff_at: datetime


class ZoneLastEvent(BaseModel):
    kind: ZoneEventKind
    at: datetime


class ZoneSensorOut(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    lat: float
    lon: float
    heading_deg: float
    range_m: float
    half_angle_deg: float
    incident_id: uuid.UUID | None
    status: ZoneSensorStatus
    battery_pct: int
    last_seen_at: datetime | None
    open_alarms: int
    last_event: ZoneLastEvent | None
    cone: list[list[float]] = Field(description="Anillo [lon, lat] del cono de vigilancia")
    source: str


class ZoneSensorList(BaseModel):
    items: list[ZoneSensorOut]
    cutoff_at: datetime


class ZoneReadingResult(BaseModel):
    events: list[ZoneEventOut]
    confirmed_incidents: list[uuid.UUID]
