"""Esquemas del módulo de recuperación (specs/003). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import AidType, DamageLevel, InspectionColor, RudStatus


class PropertyRef(BaseModel):
    """Predio: código catastral o manzana + dirección (se normaliza en la API)."""

    cadastral_code: str | None = Field(default=None, max_length=40)
    manzana_id: str | None = Field(default=None, max_length=16)
    address: str | None = Field(default=None, max_length=120)


class InspectionIn(PropertyRef):
    color: InspectionColor
    damage_level: DamageLevel
    notes: str | None = Field(default=None, max_length=500)


class InspectionOut(BaseModel):
    id: uuid.UUID
    property_id: str
    manzana_id: str | None
    barrio: str | None
    color: InspectionColor
    damage_level: DamageLevel
    notes: str | None
    inspector_role: str
    at: datetime
    visit_number: int


class PropertyOut(BaseModel):
    property_id: str
    manzana_id: str | None
    barrio: str | None
    color: InspectionColor
    damage_level: DamageLevel
    visits: int
    last_at: datetime


class PropertyList(BaseModel):
    items: list[PropertyOut]
    cutoff_at: datetime


class ManzanaRef(BaseModel):
    id: str
    barrio: str
    comuna: str


class Vulnerability(BaseModel):
    children: bool = False
    elderly: bool = False
    disability: bool = False
    pregnancy: bool = False


class HouseholdIn(PropertyRef):
    document: str = Field(
        min_length=5,
        max_length=20,
        description="Documento del jefe de hogar. Solo se usa para calcular el hash; no se guarda.",
    )
    members_count: int = Field(ge=1, le=30)
    pets_count: int = Field(default=0, ge=0, le=30)
    rud_status: RudStatus = RudStatus.pendiente
    vulnerability: Vulnerability = Vulnerability()


class HouseholdOut(BaseModel):
    id: uuid.UUID
    code: str = Field(description="Prefijo corto del hash, para mostrar")
    members_count: int
    pets_count: int
    property_id: str | None
    manzana_id: str | None
    barrio: str | None
    rud_status: RudStatus
    vulnerability: Vulnerability
    vulnerability_score: int
    aid_count: int
    created_at: datetime


class HouseholdCreated(BaseModel):
    household: HouseholdOut
    created: bool


class HouseholdList(BaseModel):
    items: list[HouseholdOut]
    cutoff_at: datetime


class LookupIn(BaseModel):
    document: str = Field(min_length=5, max_length=20)


class AidIn(BaseModel):
    document: str = Field(min_length=5, max_length=20)
    aid_type: AidType
    source_fund: str = Field(default="Fondo Municipal de Gestión del Riesgo", max_length=80)
    justification: str | None = Field(default=None, max_length=300)


class AidOut(BaseModel):
    id: uuid.UUID
    household_code: str
    aid_type: AidType
    source_fund: str
    is_duplicate: bool
    justification: str | None
    at: datetime


class AidList(BaseModel):
    items: list[AidOut]
    cutoff_at: datetime


class ShelterOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    barrio: str
    capacity: int
    people: int
    pets: int
    lat: float
    lon: float
    source: str
    updated_at: datetime


class ShelterList(BaseModel):
    items: list[ShelterOut]
    cutoff_at: datetime


class ShelterPatch(BaseModel):
    people: int = Field(ge=0)
    pets: int = Field(ge=0)


class Figure(BaseModel):
    """Cifra con trazabilidad (fuente, versión, fecha de corte). `None` = suprimida (k < 5)."""

    key: str
    label: str
    value: int | None


class RecoverySummary(BaseModel):
    source: str
    version: int
    cutoff_at: datetime
    suppressed: bool
    figures: list[Figure]


# ---------------------------------------------------------------- tablero unificado

DashUnit = Literal["conteo", "%", "dias", "cop", "mm", "magnitud"]
FigureState = Literal["ok", "alerta", "neutral"]


class DashFigure(BaseModel):
    """Cifra del tablero con nombre del diccionario de indicadores y trazabilidad."""

    key: str
    label: str
    value: float | None
    unit: DashUnit
    source: str
    version: int
    cutoff_at: datetime
    simulated: bool = True
    target: str | None = None
    state: FigureState = "neutral"


class Indicator(BaseModel):
    """Uno de los 10 indispensables (bloque encabezado, operación o economía)."""

    number: int = Field(ge=1, le=10)
    key: str
    title: str
    block: Literal["encabezado", "operacion", "economia"]
    source: str
    figures: list[DashFigure]


class Need(BaseModel):
    """Necesidad que hoy exige acción, derivada de los indicadores."""

    key: str
    title: str
    detail: str
    severity: Literal["critica", "alta", "media"]
    value: int


class BarrioRecovery(BaseModel):
    barrio: str
    comuna: str
    index: float | None
    verde: int
    amarillo: int
    rojo: int
    colapso: int
    requested: int
    pending: int
    services: dict[str, int]
    services_eta: date | None
    families: int


class CurvePoint(BaseModel):
    day: int
    value: float
    simulated: bool


class ChannelCount(BaseModel):
    channel: str
    count: int


class EconomyRow(BaseModel):
    comuna: str
    businesses_closed: int
    businesses_reopened: int
    jobs_lost: int
    jobs_recovered: int


class FundingSource(BaseModel):
    name: str
    amount_cop: float


class Stage(BaseModel):
    number: int
    title: str
    question: str
    start_day: int
    end_day: int
    status: Literal["pendiente", "verde", "amarillo", "rojo"]
    progress_pct: float | None
    figures: list[DashFigure]


class RecoveryDashboard(BaseModel):
    cutoff_at: datetime
    event_at: datetime
    day: int = Field(description="Días desde el sismo")
    index: float | None
    index_components: dict[str, float | None]
    needs: list[Need]
    indicators: list[Indicator]
    barrios: list[BarrioRecovery]
    index_curve: list[CurvePoint]
    channels: list[ChannelCount]
    economy: list[EconomyRow]
    funding: list[FundingSource]
    stages: list[Stage]
