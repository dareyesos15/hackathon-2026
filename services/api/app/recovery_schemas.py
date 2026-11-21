"""Esquemas del módulo de recuperación (specs/003). Fuente de los tipos TS."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain import (
    Affectation,
    AffectedInfrastructure,
    AidType,
    DamageLevel,
    EventStatus,
    EventType,
    HouseholdLoss,
    HousingStatus,
    InspectionColor,
    ReferralEntity,
    RespondentRelation,
    RudStatus,
    ShelterService,
    ShelterStatus,
    StructuralCause,
    Tenure,
)


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
    # Campos del RUD (UNGRD): solo conteos, nunca datos de una persona (Ley 1581).
    census_form_number: str | None = Field(
        default=None, pattern=r"^[0-9]{1,20}$", description="N.º de la planilla de censo"
    )
    tenure: Tenure | None = None
    housing_status: HousingStatus | None = Field(
        default=None, description="Si no se envía, se toma del semáforo vigente del predio"
    )
    age_0_5: int = Field(default=0, ge=0, le=30)
    age_6_17: int = Field(default=0, ge=0, le=30)
    age_18_59: int = Field(default=0, ge=0, le=30)
    age_60_plus: int = Field(default=0, ge=0, le=30)
    female_members: int = Field(default=0, ge=0, le=30)
    ethnic_members: int = Field(default=0, ge=0, le=30)
    losses: list[HouseholdLoss] = Field(default_factory=list)


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
    census_form_number: str | None = None
    tenure: Tenure | None = None
    housing_status: HousingStatus | None = None
    age_0_5: int = 0
    age_6_17: int = 0
    age_18_59: int = 0
    age_60_plus: int = 0
    female_members: int = 0
    ethnic_members: int = 0
    losses: list[HouseholdLoss] = Field(default_factory=list)
    situation: str | None = Field(
        default=None, description="albergue, arriendo, casa o sin_solucion (vivienda hoy)"
    )


class HouseholdCreated(BaseModel):
    household: HouseholdOut
    created: bool


class HouseholdList(BaseModel):
    items: list[HouseholdOut]
    cutoff_at: datetime


# ---------------------------------------------------------------- revisión a predio


class PropertyReviewIn(PropertyRef):
    """Formato GUE-RPD-FR-02 v4 "Revisión a predio" (Alcaldía de Manizales), en digital.

    Ley 1581: los nombres, teléfonos, cédulas y fechas de nacimiento del papel NO se transcriben.
    El documento del encuestado solo sirve para ligar el hogar del censo (HMAC con sal) y el del
    propietario se guarda solo como HMAC. De los residentes se registran conteos.
    """

    form_number: str | None = Field(
        default=None, pattern=r"^[0-9]{1,20}$", description="N.º impreso del formato en papel"
    )
    reviewed_at: datetime | None = Field(default=None, description="Fecha y hora del formato")
    # 2. Encuestado
    respondent_document: str | None = Field(default=None, min_length=5, max_length=20)
    respondent_relation: RespondentRelation | None = None
    owner_document: str | None = Field(default=None, min_length=5, max_length=20)
    # 3. Residentes (solo conteos)
    residents: int = Field(default=0, ge=0, le=30)
    minors: int = Field(default=0, ge=0, le=30)
    elderly: int = Field(default=0, ge=0, le=30)
    disability: int = Field(default=0, ge=0, le=30)
    pregnancy: int = Field(default=0, ge=0, le=30)
    pets: int = Field(default=0, ge=0, le=30)
    # 4. Evento
    event_status: EventStatus = EventStatus.sucedido
    event_types: list[EventType] = Field(min_length=1)
    event_other: str | None = Field(default=None, max_length=200)
    structural_causes: list[StructuralCause] = Field(default_factory=list)
    # 5. Afectación
    affectation: Affectation
    affected_areas_m2: dict[AffectedInfrastructure, float] = Field(default_factory=dict)
    belongings_loss: str | None = Field(default=None, max_length=300)
    # 6. Requiere visita
    referrals: list[ReferralEntity] = Field(default_factory=list)
    referral_other: str | None = Field(default=None, max_length=120)
    # 7. Evacuación
    evacuation_recommended: bool = False
    # Semáforo NSR-10 (si no se envía, se usa el sugerido por la afectación)
    color: InspectionColor | None = None
    damage_level: DamageLevel | None = None
    notes: str | None = Field(default=None, max_length=500)
    reviewer_agency: str = Field(default="Cuerpo Oficial de Bomberos", max_length=80)
    notified_signed: bool = False


class PropertyReviewOut(BaseModel):
    id: uuid.UUID
    form_number: str | None
    property_id: str
    barrio: str | None
    visit_number: int
    color: InspectionColor
    damage_level: DamageLevel
    suggested_color: InspectionColor
    residents: int
    respondent_relation: RespondentRelation | None
    event_status: EventStatus
    event_types: list[EventType]
    event_other: str | None
    structural_causes: list[StructuralCause]
    affectation: Affectation
    affected_areas_m2: dict[str, float]
    belongings_loss: str | None
    referrals: list[ReferralEntity]
    referrals_done: list[ReferralEntity]
    referral_other: str | None
    evacuation_recommended: bool
    reviewed_at: datetime
    reviewer_agency: str
    notified_signed: bool
    household_code: str | None
    household_created: bool
    next_steps: list[str] = Field(description="Qué sigue después de esta revisión")


class ReferralRow(BaseModel):
    review_id: uuid.UUID
    form_number: str | None
    property_id: str
    barrio: str | None
    entity: ReferralEntity
    evacuation_recommended: bool
    affectation: Affectation
    reviewed_at: datetime


class ReferralSummary(BaseModel):
    entity: ReferralEntity
    pending: int
    done: int


class ReferralList(BaseModel):
    summary: list[ReferralSummary]
    pending: list[ReferralRow]
    cutoff_at: datetime


class ReferralPatch(BaseModel):
    done: bool = True


class LookupIn(BaseModel):
    document: str = Field(min_length=5, max_length=20)


class AidIn(BaseModel):
    """Acta de entrega de ayuda humanitaria (una por entrega)."""

    document: str = Field(min_length=5, max_length=20)
    aid_type: AidType
    source_fund: str = Field(default="Fondo Municipal de Gestión del Riesgo", max_length=80)
    justification: str | None = Field(default=None, max_length=300)
    act_number: str | None = Field(
        default=None, pattern=r"^[0-9]{1,20}$", description="N.º del acta de entrega"
    )
    delivered_by: str | None = Field(default=None, max_length=80)
    quantity: int = Field(default=1, ge=1, le=100)
    amount_cop: float | None = Field(default=None, ge=0, description="Valor mensual del subsidio")
    months: int | None = Field(default=None, ge=1, le=24)
    shelter_id: uuid.UUID | None = Field(default=None, description="Albergue de destino")
    signed: bool = Field(default=False, description="El jefe de hogar firmó el acta")


class AidOut(BaseModel):
    id: uuid.UUID
    household_code: str
    aid_type: AidType
    source_fund: str
    is_duplicate: bool
    justification: str | None
    at: datetime
    act_number: str | None = None
    delivered_by: str | None = None
    quantity: int = 1
    amount_cop: float | None = None
    months: int | None = None
    shelter_id: uuid.UUID | None = None
    shelter_name: str | None = None
    signed: bool = False
    ended_at: datetime | None = None
    members: int = 0


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
    operator: str | None = None
    status: ShelterStatus = ShelterStatus.abierto
    services: list[ShelterService] = Field(default_factory=list)
    families: int = Field(default=0, description="Hogares del censo alojados hoy")


class ShelterList(BaseModel):
    items: list[ShelterOut]
    cutoff_at: datetime


class ShelterPatch(BaseModel):
    """Ajustes del albergue. La ocupación sube y baja sola con las entradas y salidas de hogares;
    `people`/`pets` solo corrigen el conteo (p. ej. personas no censadas)."""

    people: int | None = Field(default=None, ge=0)
    pets: int | None = Field(default=None, ge=0)
    operator: str | None = Field(default=None, max_length=120)
    status: ShelterStatus | None = None
    services: list[ShelterService] | None = None


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
FigureState = Literal["ok", "alerta", "neutral", "sin_fuente"]


class DashFigure(BaseModel):
    """Cifra del tablero con nombre del diccionario de indicadores y su respaldo.

    `state = "sin_fuente"`: no hay fuente conectada; `value` es `None` y `note` dice qué entidad
    o convenio la provee. Nunca se muestra un número inventado.
    """

    key: str
    label: str
    value: float | None
    unit: DashUnit
    source: str
    version: int
    cutoff_at: datetime
    simulated: bool = False
    target: str | None = None
    state: FigureState = "neutral"
    source_url: str | None = None
    note: str | None = None


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
    damage_reported: int = Field(description="Manzanas con daño reportado por la ciudadanía")
    pending: int = Field(description="De esas manzanas, las que aún no tienen evaluación")
    service_incidents: int = Field(description="Incidentes abiertos de servicios caídos")
    families: int


class CurvePoint(BaseModel):
    at: datetime
    day: int
    value: float


class ChannelCount(BaseModel):
    channel: str
    count: int


class ContractRow(BaseModel):
    """Contrato de SECOP II ligado al sismo (sin datos personales del contratista)."""

    id: str
    entity: str
    signed_at: date | None
    status: str
    object: str
    value_cop: float
    invoiced_cop: float
    paid_cop: float
    url: str | None


class SourceInfo(BaseModel):
    """Respaldo de una fuente: de dónde sale, cuándo se consultó y si la copia está íntegra."""

    key: str
    title: str
    source: str
    status: Literal["conectada", "sin_copia", "sin_convenio"]
    query_url: str | None = None
    license: str | None = None
    attribution: str | None = None
    fetched_at: datetime | None = None
    record_count: int | None = None
    sha256: str | None = None
    verified: bool | None = None
    feeds: str = Field(description="Indicadores que alimenta")


class Stage(BaseModel):
    number: int
    title: str
    question: str
    start_day: int
    end_day: int
    status: Literal["pendiente", "verde", "amarillo", "rojo", "sin_fuente"]
    progress_pct: float | None
    progress_basis: str | None = Field(default=None, description="Cómo se mide el avance")
    figures: list[DashFigure]


class RecoveryDashboard(BaseModel):
    cutoff_at: datetime
    event_at: datetime | None
    event_label: str | None
    event_url: str | None
    day: int = Field(description="Días desde el sismo principal")
    index: float | None
    index_components: dict[str, float | None]
    needs: list[Need]
    indicators: list[Indicator]
    barrios: list[BarrioRecovery]
    index_curve: list[CurvePoint]
    channels: list[ChannelCount]
    contracts: list[ContractRow]
    sources: list[SourceInfo]
    stages: list[Stage]
