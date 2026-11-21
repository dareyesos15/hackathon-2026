"""Revisión a predio (formato GUE-RPD-FR-02 v4 de la Alcaldía de Manizales).

Un solo envío alimenta todo el módulo de recuperación:
1. Evaluación de habitabilidad (semáforo NSR-10) del predio único: el semáforo se sugiere con la
   afectación y la evacuación, y se rechazan combinaciones incoherentes.
2. Hogar del censo único: se crea o se liga por HMAC del documento del encuestado (sin duplicar).
3. Derivaciones a entidades (sección 6 "Requiere visita"), pendientes hasta marcarlas atendidas.
4. Evacuación recomendada: queda como necesidad del tablero hasta que el hogar reciba albergue o
   subsidio de arriendo, con la ruta de la Cruz Roja.

Ley 1581: no se guardan nombres, teléfonos, cédulas ni fechas de nacimiento; los textos libres se
redactan antes de persistir.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.config import get_settings
from app.core.privacy import redact
from app.core.recovery import (
    consistent,
    household_hash,
    owner_hash,
    review_inconsistency,
    suggest_semaphore,
)
from app.db import get_session
from app.domain import Affectation, ReferralEntity, Role, RudStatus
from app.models import BuildingInspection, Household, HouseholdVulnerability, PropertyReview
from app.recovery_schemas import (
    PropertyReviewIn,
    PropertyReviewOut,
    ReferralList,
    ReferralPatch,
    ReferralRow,
    ReferralSummary,
)
from app.routers.recovery import FIELD, SOURCE, _barrios, _error, _resolve_property

router = APIRouter(prefix="/recovery", tags=["recuperación"])

REFERRAL_ROLES = (*FIELD, Role.agencia)
CRUZ_ROJA = (
    "Evacuación recomendada: orientar a la familia a la Cruz Roja Colombiana Seccional Caldas "
    "(886 6300) para el auxilio de arrendamiento o la ayuda humanitaria, con fotocopia de esta "
    "revisión y de la cédula del titular; luego registrar la ayuda en la pestaña Ayudas."
)
ENTITY_LABEL = {
    ReferralEntity.ugr: "UGR",
    ReferralEntity.corpocaldas: "Corpocaldas",
    ReferralEntity.aguas_de_manizales: "Aguas de Manizales",
    ReferralEntity.obras_publicas: "Obras Públicas Municipales",
    ReferralEntity.invias: "Invías",
    ReferralEntity.chec: "CHEC",
    ReferralEntity.invama: "Invama",
    ReferralEntity.planeacion: "Planeación",
    ReferralEntity.infraestructura_depto: "Sec. Infraestructura Depto.",
    ReferralEntity.inspeccion_policia: "Inspección de Policía",
    ReferralEntity.otro: "Otra entidad",
}


def _clean(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    return redact(text.strip()).text


async def _out(
    session: AsyncSession,
    review: PropertyReview,
    inspection: BuildingInspection,
    *,
    household: Household | None,
    household_created: bool,
    next_steps: list[str],
) -> PropertyReviewOut:
    visits = await session.scalar(
        select(func.count())
        .select_from(BuildingInspection)
        .where(
            BuildingInspection.property_id == review.property_id,
            BuildingInspection.at <= inspection.at,
        )
    )
    barrios = await _barrios(session, {inspection.manzana_id})
    suggested, _ = suggest_semaphore(review.affectation, review.evacuation_recommended)
    return PropertyReviewOut(
        id=review.id,
        form_number=review.form_number,
        property_id=review.property_id,
        barrio=barrios.get(inspection.manzana_id or ""),
        visit_number=visits or 1,
        color=inspection.color,
        damage_level=inspection.damage_level,
        suggested_color=suggested,
        residents=review.residents,
        respondent_relation=review.respondent_relation,  # type: ignore[arg-type]
        event_status=review.event_status,  # type: ignore[arg-type]
        event_types=review.event_types,  # type: ignore[arg-type]
        event_other=review.event_other,
        structural_causes=review.structural_causes,  # type: ignore[arg-type]
        affectation=review.affectation,  # type: ignore[arg-type]
        affected_areas_m2=review.affected_areas_m2,
        belongings_loss=review.belongings_loss,
        referrals=review.referrals,  # type: ignore[arg-type]
        referrals_done=review.referrals_done,  # type: ignore[arg-type]
        referral_other=review.referral_other,
        evacuation_recommended=review.evacuation_recommended,
        reviewed_at=review.reviewed_at,
        reviewer_agency=review.reviewer_agency,
        notified_signed=review.notified_signed,
        household_code=household.household_hash[:8].upper() if household else None,
        household_created=household_created,
        next_steps=next_steps,
    )


@router.post(
    "/reviews",
    response_model=PropertyReviewOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Ese N.º de formato ya fue registrado"}},
)
async def post_review(
    body: PropertyReviewIn,
    role: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> PropertyReviewOut:
    """Registra un formato de revisión a predio y alimenta habitabilidad, censo y derivaciones."""
    settings = get_settings()
    if body.form_number:
        existing = await session.scalar(
            select(PropertyReview.property_id).where(PropertyReview.form_number == body.form_number)
        )
        if existing:
            raise _error(
                409,
                f"El formato N.º {body.form_number} ya está registrado (predio {existing})",
                "duplicate_form",
            )
    if body.minors + body.elderly > body.residents and body.residents:
        raise _error(422, "Hay más menores y mayores que residentes", "inconsistent_residents")
    suggested_color, suggested_damage = suggest_semaphore(
        body.affectation.value, body.evacuation_recommended
    )
    color = body.color or suggested_color
    damage = body.damage_level or suggested_damage
    if not consistent(color, damage):
        raise _error(
            422, "El color del semáforo no corresponde al nivel de daño", "inconsistent_damage"
        )
    problem = review_inconsistency(color, body.affectation.value, body.evacuation_recommended)
    if problem:
        raise _error(422, problem, "inconsistent_review")

    key, manzana_id = await _resolve_property(session, body)
    reviewed_at = body.reviewed_at or datetime.now(UTC)
    inspection = BuildingInspection(
        property_id=key,
        manzana_id=manzana_id,
        color=color,
        damage_level=damage,
        notes=_clean(body.notes),
        inspector_role=role.value,
        at=reviewed_at,
        source=SOURCE,
    )
    session.add(inspection)
    await session.flush()

    # Censo único: ligar o crear el hogar sin duplicar (HMAC del documento del encuestado).
    household: Household | None = None
    created = False
    if body.respondent_document:
        try:
            digest = household_hash(body.respondent_document, salt=settings.pii_salt)
        except ValueError as err:
            raise _error(422, str(err), "invalid_document") from err
        household = (
            await session.execute(select(Household).where(Household.household_hash == digest))
        ).scalar_one_or_none()
        if household is None:
            household = Household(
                household_hash=digest,
                members_count=max(body.residents, 1),
                pets_count=body.pets,
                property_id=key,
                manzana_id=manzana_id,
                rud_status=RudStatus.pendiente,
                source=SOURCE,
            )
            session.add(household)
            await session.flush()
            session.add(
                HouseholdVulnerability(
                    household_id=household.id,
                    children=body.minors > 0,
                    elderly=body.elderly > 0,
                    disability=body.disability > 0,
                    pregnancy=body.pregnancy > 0,
                )
            )
            created = True
        elif household.property_id is None:
            household.property_id = key
            household.manzana_id = household.manzana_id or manzana_id

    owner = None
    if body.owner_document:
        try:
            owner = owner_hash(body.owner_document, salt=settings.pii_salt)
        except ValueError as err:
            raise _error(422, str(err), "invalid_document") from err
    review = PropertyReview(
        form_number=body.form_number,
        inspection_id=inspection.id,
        property_id=key,
        household_id=household.id if household else None,
        respondent_relation=body.respondent_relation.value if body.respondent_relation else None,
        owner_hash=owner,
        residents=body.residents,
        event_status=body.event_status.value,
        event_types=sorted({e.value for e in body.event_types}),
        event_other=_clean(body.event_other),
        structural_causes=sorted({c.value for c in body.structural_causes}),
        affectation=body.affectation.value,
        affected_areas_m2={
            k.value: round(v, 1) for k, v in body.affected_areas_m2.items() if v > 0
        },
        belongings_loss=_clean(body.belongings_loss),
        referrals=sorted({r.value for r in body.referrals}),
        referral_other=_clean(body.referral_other),
        referrals_done=[],
        evacuation_recommended=body.evacuation_recommended,
        reviewed_at=reviewed_at,
        reviewer_agency=body.reviewer_agency.strip() or "Cuerpo Oficial de Bomberos",
        notified_signed=body.notified_signed,
        recorded_by_role=role.value,
        source=SOURCE,
    )
    session.add(review)
    await session.flush()

    steps: list[str] = []
    visits = await session.scalar(
        select(func.count())
        .select_from(BuildingInspection)
        .where(BuildingInspection.property_id == key)
    )
    if visits and visits > 1:
        steps.append(f"Predio ya revisado: esta es la visita n.º {visits}, unida al mismo predio.")
    if household and created:
        steps.append(
            f"Hogar {household.household_hash[:8].upper()} creado en el censo único "
            f"({max(body.residents, 1)} personas). Inscríbalo en el RUD desde Censo único."
        )
    elif household:
        steps.append(
            f"Hogar {household.household_hash[:8].upper()} ya estaba en el censo: se ligó a esta "
            "revisión sin duplicarlo."
        )
    else:
        steps.append(
            "Sin documento del encuestado: el hogar no quedó en el censo. Regístrelo en Censo "
            "único si la familia está damnificada."
        )
    if body.evacuation_recommended:
        steps.append(CRUZ_ROJA)
    if body.referrals:
        names = ", ".join(ENTITY_LABEL[r] for r in sorted(set(body.referrals)))
        steps.append(
            f"Derivado a: {names}. Queda pendiente hasta que cada entidad marque su visita."
        )
    await session.commit()
    bus.publish("recovery.updated", {"kind": "review"})
    return await _out(
        session,
        review,
        inspection,
        household=household,
        household_created=created,
        next_steps=steps,
    )


@router.get("/reviews", response_model=list[PropertyReviewOut])
async def list_reviews(
    property_id: str | None = None,
    _: Role = Depends(require_role(*FIELD)),
    session: AsyncSession = Depends(get_session),
) -> list[PropertyReviewOut]:
    """Formatos registrados (de un predio, o los últimos 200)."""
    stmt = (
        select(PropertyReview, BuildingInspection, Household)
        .join(BuildingInspection, BuildingInspection.id == PropertyReview.inspection_id)
        .outerjoin(Household, Household.id == PropertyReview.household_id)
        .order_by(PropertyReview.reviewed_at.desc())
        .limit(200)
    )
    if property_id:
        stmt = stmt.where(PropertyReview.property_id == property_id)
    rows = (await session.execute(stmt)).all()
    return [
        await _out(session, r, i, household=h, household_created=False, next_steps=[])
        for r, i, h in rows
    ]


@router.get("/referrals", response_model=ReferralList)
async def list_referrals(
    _: Role = Depends(require_role(*REFERRAL_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ReferralList:
    """Derivaciones de la sección 6 por entidad: pendientes y atendidas."""
    rows = (
        await session.execute(
            select(PropertyReview, BuildingInspection.manzana_id)
            .join(BuildingInspection, BuildingInspection.id == PropertyReview.inspection_id)
            .where(func.cardinality(PropertyReview.referrals) > 0)
            .order_by(PropertyReview.evacuation_recommended.desc(), PropertyReview.reviewed_at)
        )
    ).all()
    barrios = await _barrios(session, {m for _, m in rows})
    counts: dict[str, list[int]] = {}
    pending: list[ReferralRow] = []
    for review, manzana in rows:
        for entity in review.referrals:
            done = entity in review.referrals_done
            counts.setdefault(entity, [0, 0])[1 if done else 0] += 1
            if not done:
                pending.append(
                    ReferralRow(
                        review_id=review.id,
                        form_number=review.form_number,
                        property_id=review.property_id,
                        barrio=barrios.get(manzana or ""),
                        entity=ReferralEntity(entity),
                        evacuation_recommended=review.evacuation_recommended,
                        affectation=Affectation(review.affectation),
                        reviewed_at=review.reviewed_at,
                    )
                )
    summary = [
        ReferralSummary(entity=ReferralEntity(e), pending=p, done=d)
        for e, (p, d) in sorted(counts.items(), key=lambda kv: -kv[1][0])
    ]
    return ReferralList(summary=summary, pending=pending, cutoff_at=datetime.now(UTC))


@router.patch("/reviews/{review_id}/referrals/{entity}", response_model=ReferralSummary)
async def patch_referral(
    review_id: uuid.UUID,
    entity: ReferralEntity,
    body: ReferralPatch,
    _: Role = Depends(require_role(*REFERRAL_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> ReferralSummary:
    """Marca (o desmarca) la visita de una entidad derivada."""
    review = await session.get(PropertyReview, review_id)
    if review is None:
        raise _error(404, "La revisión no existe", "not_found")
    if entity.value not in review.referrals:
        raise _error(422, "Esa entidad no fue derivada en esta revisión", "not_referred")
    done = set(review.referrals_done)
    if body.done:
        done.add(entity.value)
    else:
        done.discard(entity.value)
    review.referrals_done = sorted(done)
    review.version += 1
    await session.commit()
    bus.publish("recovery.updated", {"kind": "referral"})
    return ReferralSummary(
        entity=entity,
        pending=int(entity.value not in done),
        done=int(entity.value in done),
    )
