"""Recuperación post-sismo (specs/003): habitabilidad, censo único, ayudas y albergues.

Habeas Data: el documento del hogar solo se usa para calcular un HMAC con sal y nunca se
guarda; la vulnerabilidad vive en una tabla separada visible solo para PMU/COE; el rol
`publico` recibe agregados con supresión k ≥ 5.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from geoalchemy2.shape import to_shape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.config import get_settings
from app.core.recovery import (
    consistent,
    household_hash,
    is_duplicate_aid,
    property_key,
    suppress,
)
from app.db import get_session
from app.domain import InspectionColor, Role, RudStatus
from app.models import (
    AidDelivery,
    BuildingInspection,
    Household,
    HouseholdVulnerability,
    Manzana,
    Shelter,
)
from app.recovery_schemas import (
    AidIn,
    AidList,
    AidOut,
    Figure,
    HouseholdCreated,
    HouseholdIn,
    HouseholdList,
    HouseholdOut,
    InspectionIn,
    InspectionOut,
    LookupIn,
    ManzanaRef,
    PropertyList,
    PropertyOut,
    PropertyRef,
    RecoverySummary,
    ShelterList,
    ShelterOut,
    ShelterPatch,
    Vulnerability,
)

router = APIRouter(prefix="/recovery", tags=["recuperación"])

FIELD = (Role.inspector, Role.operador_pmu, Role.coe)
PMU = (Role.operador_pmu, Role.coe)
SOURCE = "Módulo de recuperación Dacora (SIMULADO)"


def _error(code: int, detail: str, kind: str) -> HTTPException:
    return HTTPException(code, detail={"detail": detail, "code": kind})


async def _resolve_property(session: AsyncSession, ref: PropertyRef) -> tuple[str, str | None]:
    if ref.manzana_id and await session.get(Manzana, ref.manzana_id) is None:
        raise _error(422, "La manzana no existe", "manzana_not_found")
    try:
        key = property_key(
            cadastral_code=ref.cadastral_code, manzana_id=ref.manzana_id, address=ref.address
        )
    except ValueError as err:
        raise _error(422, str(err), "property_required") from err
    return key, ref.manzana_id


async def _barrios(session: AsyncSession, ids: set[str | None]) -> dict[str, str]:
    clean = {i for i in ids if i}
    if not clean:
        return {}
    rows = await session.execute(select(Manzana.id, Manzana.barrio).where(Manzana.id.in_(clean)))
    return {mid: barrio for mid, barrio in rows.all()}


# ---------------------------------------------------------------- manzanas (selector)


@router.get("/manzanas", response_model=list[ManzanaRef])
async def list_manzanas(
    _: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> list[ManzanaRef]:
    rows = await session.execute(
        select(Manzana.id, Manzana.barrio, Manzana.comuna).order_by(Manzana.barrio, Manzana.id)
    )
    return [ManzanaRef(id=i, barrio=b, comuna=c) for i, b, c in rows.all()]


# ---------------------------------------------------------------- habitabilidad


@router.post("/inspections", response_model=InspectionOut, status_code=status.HTTP_201_CREATED)
async def post_inspection(
    body: InspectionIn,
    role: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> InspectionOut:
    if not consistent(body.color, body.damage_level):
        raise _error(
            422, "El color del semáforo no corresponde al nivel de daño", "inconsistent_damage"
        )
    key, manzana_id = await _resolve_property(session, body)
    inspection = BuildingInspection(
        property_id=key,
        manzana_id=manzana_id,
        color=body.color,
        damage_level=body.damage_level,
        notes=body.notes,
        inspector_role=role.value,
        at=datetime.now(UTC),
        source=SOURCE,
    )
    session.add(inspection)
    await session.flush()
    visits = await session.scalar(
        select(func.count())
        .select_from(BuildingInspection)
        .where(BuildingInspection.property_id == key)
    )
    await session.commit()
    barrios = await _barrios(session, {manzana_id})
    bus.publish("recovery.updated", {"kind": "inspection"})
    return InspectionOut(
        id=inspection.id,
        property_id=key,
        manzana_id=manzana_id,
        barrio=barrios.get(manzana_id or ""),
        color=inspection.color,
        damage_level=inspection.damage_level,
        notes=inspection.notes,
        inspector_role=inspection.inspector_role,
        at=inspection.at,
        visit_number=visits or 1,
    )


@router.get("/properties", response_model=PropertyList)
async def list_properties(
    color: InspectionColor | None = None,
    _: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> PropertyList:
    """Estado vigente por predio (última evaluación) y número de visitas."""
    ranked = select(
        BuildingInspection,
        func.row_number()
        .over(
            partition_by=BuildingInspection.property_id,
            order_by=(BuildingInspection.at.desc(), BuildingInspection.created_at.desc()),
        )
        .label("rn"),
        func.count().over(partition_by=BuildingInspection.property_id).label("visits"),
    ).subquery()
    stmt = (
        select(
            ranked.c.property_id,
            ranked.c.manzana_id,
            ranked.c.color,
            ranked.c.damage_level,
            ranked.c.visits,
            ranked.c.at,
        )
        .where(ranked.c.rn == 1)
        .order_by(ranked.c.at.desc())
        .limit(500)
    )
    if color:
        stmt = stmt.where(ranked.c.color == color.value)
    rows = (await session.execute(stmt)).all()
    barrios = await _barrios(session, {r.manzana_id for r in rows})
    return PropertyList(
        items=[
            PropertyOut(
                property_id=r.property_id,
                manzana_id=r.manzana_id,
                barrio=barrios.get(r.manzana_id or ""),
                color=r.color,
                damage_level=r.damage_level,
                visits=r.visits,
                last_at=r.at,
            )
            for r in rows
        ],
        cutoff_at=datetime.now(UTC),
    )


@router.get("/inspections", response_model=list[InspectionOut])
async def list_inspections(
    property_id: str,
    _: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> list[InspectionOut]:
    """Historial de visitas de un predio (trazabilidad solicitud → visita → clasificación)."""
    rows = list(
        (
            await session.execute(
                select(BuildingInspection)
                .where(BuildingInspection.property_id == property_id)
                .order_by(BuildingInspection.at)
            )
        ).scalars()
    )
    barrios = await _barrios(session, {r.manzana_id for r in rows})
    return [
        InspectionOut(
            id=r.id,
            property_id=r.property_id,
            manzana_id=r.manzana_id,
            barrio=barrios.get(r.manzana_id or ""),
            color=r.color,
            damage_level=r.damage_level,
            notes=r.notes,
            inspector_role=r.inspector_role,
            at=r.at,
            visit_number=n,
        )
        for n, r in enumerate(rows, start=1)
    ]


# ---------------------------------------------------------------- censo único


async def _households_out(
    session: AsyncSession, households: Sequence[Household]
) -> list[HouseholdOut]:
    ids = [h.id for h in households]
    if not ids:
        return []
    vulns = {
        v.household_id: v
        for v in (
            await session.execute(
                select(HouseholdVulnerability).where(HouseholdVulnerability.household_id.in_(ids))
            )
        ).scalars()
    }
    aid = dict(
        (
            await session.execute(
                select(AidDelivery.household_id, func.count())
                .where(AidDelivery.household_id.in_(ids))
                .group_by(AidDelivery.household_id)
            )
        ).all()
    )
    barrios = await _barrios(session, {h.manzana_id for h in households})
    out: list[HouseholdOut] = []
    for h in households:
        v = vulns.get(h.id)
        vuln = Vulnerability(
            children=bool(v and v.children),
            elderly=bool(v and v.elderly),
            disability=bool(v and v.disability),
            pregnancy=bool(v and v.pregnancy),
        )
        out.append(
            HouseholdOut(
                id=h.id,
                code=h.household_hash[:8].upper(),
                members_count=h.members_count,
                pets_count=h.pets_count,
                property_id=h.property_id,
                manzana_id=h.manzana_id,
                barrio=barrios.get(h.manzana_id or ""),
                rud_status=h.rud_status,
                vulnerability=vuln,
                vulnerability_score=sum(vuln.model_dump().values()),
                aid_count=int(aid.get(h.id, 0)),
                created_at=h.created_at,
            )
        )
    return out


async def _household_by_document(session: AsyncSession, document: str) -> Household | None:
    try:
        digest = household_hash(document, salt=get_settings().pii_salt)
    except ValueError as err:
        raise _error(422, str(err), "invalid_document") from err
    return (
        await session.execute(select(Household).where(Household.household_hash == digest))
    ).scalar_one_or_none()


@router.post(
    "/households",
    response_model=HouseholdCreated,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Hogar ya registrado: se devuelve el existente"}},
)
async def post_household(
    body: HouseholdIn,
    response: Response,
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdCreated:
    existing = await _household_by_document(session, body.document)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return HouseholdCreated(
            household=(await _households_out(session, [existing]))[0], created=False
        )
    property_id: str | None = None
    manzana_id = body.manzana_id
    if body.cadastral_code or (body.manzana_id and body.address):
        property_id, manzana_id = await _resolve_property(session, body)
    elif manzana_id and await session.get(Manzana, manzana_id) is None:
        raise _error(422, "La manzana no existe", "manzana_not_found")
    household = Household(
        household_hash=household_hash(body.document, salt=get_settings().pii_salt),
        members_count=body.members_count,
        pets_count=body.pets_count,
        property_id=property_id,
        manzana_id=manzana_id,
        rud_status=body.rud_status,
        source=SOURCE,
    )
    session.add(household)
    await session.flush()
    session.add(
        HouseholdVulnerability(household_id=household.id, **body.vulnerability.model_dump())
    )
    await session.commit()
    bus.publish("recovery.updated", {"kind": "household"})
    return HouseholdCreated(
        household=(await _households_out(session, [household]))[0], created=True
    )


@router.get("/households", response_model=HouseholdList)
async def list_households(
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdList:
    households = list(
        (
            await session.execute(
                select(Household).order_by(Household.created_at.desc()).limit(500)
            )
        ).scalars()
    )
    return HouseholdList(
        items=await _households_out(session, households), cutoff_at=datetime.now(UTC)
    )


@router.post("/households/lookup", response_model=HouseholdOut)
async def lookup_household(
    body: LookupIn,
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdOut:
    """Busca un hogar por documento (POST para que el documento no quede en URLs ni logs)."""
    household = await _household_by_document(session, body.document)
    if household is None:
        raise _error(404, "Hogar no registrado en el censo", "not_found")
    return (await _households_out(session, [household]))[0]


@router.patch("/households/{household_id}/rud", response_model=HouseholdOut)
async def set_rud(
    household_id: uuid.UUID,
    rud_status: RudStatus,
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> HouseholdOut:
    household = await session.get(Household, household_id)
    if household is None:
        raise _error(404, "Hogar no existe", "not_found")
    household.rud_status = rud_status
    household.version += 1
    await session.commit()
    return (await _households_out(session, [household]))[0]


RUD_COLUMNS = [
    "codigo_hogar",
    "manzana",
    "barrio",
    "predio",
    "integrantes",
    "mascotas",
    "estado_rud",
    "indice_vulnerabilidad",
    "ayudas_recibidas",
    "fecha_registro",
]


@router.get("/households/export.csv", response_class=StreamingResponse)
async def export_households(
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Exportación tipo RUD (UNGRD), sin datos personales: solo el código derivado del hash."""
    households = list(
        (await session.execute(select(Household).order_by(Household.created_at))).scalars()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(RUD_COLUMNS)
    for h in await _households_out(session, households):
        writer.writerow(
            [
                h.code,
                h.manzana_id or "",
                h.barrio or "",
                h.property_id or "",
                h.members_count,
                h.pets_count,
                h.rud_status.value,
                h.vulnerability_score,
                h.aid_count,
                h.created_at.isoformat(),
            ]
        )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M")
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="censo_rud_{stamp}.csv"'},
    )


# ---------------------------------------------------------------- ayudas


def _aid_out(aid: AidDelivery, household: Household) -> AidOut:
    return AidOut(
        id=aid.id,
        household_code=household.household_hash[:8].upper(),
        aid_type=aid.aid_type,
        source_fund=aid.source_fund,
        is_duplicate=aid.is_duplicate,
        justification=aid.justification,
        at=aid.at,
    )


@router.post("/aid", response_model=AidOut, status_code=status.HTTP_201_CREATED)
async def post_aid(
    body: AidIn,
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> AidOut:
    """Bloquea la misma ayuda al mismo hogar dentro de su ventana, salvo justificación."""
    household = await _household_by_document(session, body.document)
    if household is None:
        raise _error(404, "Hogar no registrado en el censo: regístrelo primero", "not_found")
    now = datetime.now(UTC)
    previous = list(
        (
            await session.execute(
                select(AidDelivery.at).where(
                    AidDelivery.household_id == household.id,
                    AidDelivery.aid_type == body.aid_type,
                )
            )
        ).scalars()
    )
    duplicate = is_duplicate_aid(body.aid_type, previous, now)
    justification = (body.justification or "").strip() or None
    if duplicate and justification is None:
        raise _error(
            409,
            "Este hogar ya recibió esta ayuda en el periodo vigente. Justifique para entregarla.",
            "aid_duplicate",
        )
    aid = AidDelivery(
        household_id=household.id,
        aid_type=body.aid_type,
        source_fund=body.source_fund,
        is_duplicate=duplicate,
        justification=justification if duplicate else None,
        at=now,
        source=SOURCE,
    )
    session.add(aid)
    await session.commit()
    bus.publish("recovery.updated", {"kind": "aid"})
    return _aid_out(aid, household)


@router.get("/aid", response_model=AidList)
async def list_aid(
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> AidList:
    rows = (
        await session.execute(
            select(AidDelivery, Household)
            .join(Household, Household.id == AidDelivery.household_id)
            .order_by(AidDelivery.at.desc())
            .limit(300)
        )
    ).all()
    return AidList(items=[_aid_out(a, h) for a, h in rows], cutoff_at=datetime.now(UTC))


# ---------------------------------------------------------------- albergues


def _shelter_out(s: Shelter) -> ShelterOut:
    point = to_shape(s.geom)
    return ShelterOut(
        id=s.id,
        code=s.code,
        name=s.name,
        barrio=s.barrio,
        capacity=s.capacity,
        people=s.people,
        pets=s.pets,
        lat=point.y,
        lon=point.x,
        source=s.source,
        updated_at=s.updated_at,
    )


@router.get("/shelters", response_model=ShelterList)
async def list_shelters(
    _: Role = Depends(require_role(*PMU, Role.publico, Role.ciudadano)),
    session: AsyncSession = Depends(get_session),
) -> ShelterList:
    """Albergues con ocupación (agregados por sitio, sin datos de personas)."""
    shelters = (await session.execute(select(Shelter).order_by(Shelter.name))).scalars()
    return ShelterList(items=[_shelter_out(s) for s in shelters], cutoff_at=datetime.now(UTC))


@router.patch("/shelters/{shelter_id}", response_model=ShelterOut)
async def patch_shelter(
    shelter_id: uuid.UUID,
    body: ShelterPatch,
    _: Role = Depends(require_role(*PMU)),
    session: AsyncSession = Depends(get_session),
) -> ShelterOut:
    shelter = await session.get(Shelter, shelter_id)
    if shelter is None:
        raise _error(404, "Albergue no existe", "not_found")
    if body.people > shelter.capacity:
        raise _error(422, "La ocupación supera la capacidad del albergue", "over_capacity")
    shelter.people = body.people
    shelter.pets = body.pets
    shelter.version += 1
    shelter.updated_at = datetime.now(UTC)
    await session.commit()
    bus.publish("recovery.updated", {"kind": "shelter"})
    return _shelter_out(shelter)


# ---------------------------------------------------------------- resumen


@router.get("/summary", response_model=RecoverySummary)
async def summary(
    role: Role = Depends(require_role(*FIELD, Role.publico, Role.ciudadano)),
    session: AsyncSession = Depends(get_session),
) -> RecoverySummary:
    """Cifras de recuperación con fuente y fecha de corte. Público: supresión k ≥ 5."""
    latest = (
        select(
            BuildingInspection.property_id,
            BuildingInspection.color,
            func.row_number()
            .over(
                partition_by=BuildingInspection.property_id,
                order_by=(BuildingInspection.at.desc(), BuildingInspection.created_at.desc()),
            )
            .label("rn"),
        )
    ).subquery()
    by_color: dict[str, int] = dict(
        (
            await session.execute(
                select(latest.c.color, func.count())
                .where(latest.c.rn == 1)
                .group_by(latest.c.color)
            )
        ).all()
    )
    visits = await session.scalar(select(func.count()).select_from(BuildingInspection)) or 0
    hh_count, people, pets, rud = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Household.members_count), 0),
                func.coalesce(func.sum(Household.pets_count), 0),
                func.count().filter(Household.rud_status == RudStatus.inscrito),
            ).select_from(Household)
        )
    ).one()
    aid_total, aid_dup = (
        await session.execute(
            select(func.count(), func.count().filter(AidDelivery.is_duplicate)).select_from(
                AidDelivery
            )
        )
    ).one()
    sh_capacity, sh_people, sh_pets = (
        await session.execute(
            select(
                func.coalesce(func.sum(Shelter.capacity), 0),
                func.coalesce(func.sum(Shelter.people), 0),
                func.coalesce(func.sum(Shelter.pets), 0),
            )
        )
    ).one()
    properties = sum(by_color.values())
    raw = [
        ("predios_evaluados", "Predios evaluados", properties),
        ("visitas", "Visitas de inspección", visits),
        ("predios_verde", "Predios habitables (verde)", by_color.get("verde", 0)),
        ("predios_amarillo", "Uso restringido (amarillo)", by_color.get("amarillo", 0)),
        ("predios_rojo", "No habitables (rojo)", by_color.get("rojo", 0)),
        ("hogares", "Hogares en el censo único", hh_count),
        ("personas", "Personas damnificadas", people),
        ("rud_inscritos", "Hogares inscritos en el RUD", rud),
        ("ayudas", "Ayudas entregadas", aid_total),
        ("ayudas_duplicadas", "Ayudas repetidas con justificación", aid_dup),
        ("albergue_personas", "Personas en albergue", sh_people),
        ("albergue_mascotas", "Mascotas en albergue", sh_pets),
        ("albergue_capacidad", "Capacidad de albergues", sh_capacity),
    ]
    public = role in (Role.publico, Role.ciudadano)
    k = get_settings().k_anonymity
    figures = [
        Figure(
            key=key,
            label=label,
            value=suppress(int(value), k)
            if public and key not in {"albergue_capacidad"}
            else int(value),
        )
        for key, label, value in raw
    ]
    return RecoverySummary(
        source=SOURCE, version=1, cutoff_at=datetime.now(UTC), suppressed=public, figures=figures
    )
