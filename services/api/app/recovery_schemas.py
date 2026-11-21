"""Esquemas del módulo de recuperación (specs/003). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import datetime

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
