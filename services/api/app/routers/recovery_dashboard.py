"""Tablero de recuperación unificado: los 10 indispensables, necesidades y ciclo económico.

Regla de oro: cada cifra lleva su nombre del diccionario de indicadores, fuente, versión y hora de
corte, y se cuentan predios únicos, no visitas. **Ninguna cifra es inventada**: sale del registro
de Dacora (base de datos, con bitácora) o de la copia fechada y con huella SHA-256 de una fuente
pública (USGS, SECOP II, CDIAC; ver app/adapters/public_sources.py). Lo que no tiene fuente
conectada se muestra como "sin fuente" con la entidad que la provee, nunca con un número.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.public_sources import LoadedSnapshot, load_snapshot
from app.adapters.rain import CDIAC_SOURCE
from app.auth import require_role
from app.config import get_settings
from app.core.recovery_dashboard import (
    STAGES,
    habitability_score,
    household_situation,
    pct,
    recovery_index,
    stage_status,
)
from app.db import get_session
from app.domain import AidType, Category, ReportStatus, Role
from app.models import (
    AidDelivery,
    BuildingInspection,
    Household,
    HouseholdVulnerability,
    Incident,
    Manzana,
    MetricSnapshot,
    PropertyReview,
    RainReading,
    Report,
    Shelter,
)
from app.recovery_schemas import (
    BarrioRecovery,
    ChannelCount,
    ContractRow,
    CurvePoint,
    DashFigure,
    DashUnit,
    FigureState,
    Indicator,
    Need,
    RecoveryDashboard,
    SourceInfo,
    Stage,
)

router = APIRouter(prefix="/recovery", tags=["recuperación"])

HOUSING_AID = (AidType.albergue, AidType.subsidio_arriendo)
DAMAGE = (Category.colapso_estructura, Category.dano_estructural)
CLOSED_REPORT = (ReportStatus.descartado, ReportStatus.atendido)

#: Fuentes que aún no tienen acceso público: se nombran, no se inventan.
NO_SOURCE: dict[str, tuple[str, str, str]] = {
    "servicios": (
        "Cobertura de agua, energía, gas, telecomunicaciones y vías por barrio",
        "Aguas de Manizales, CHEC, Efigas y Secretaría de Obras Públicas",
        "6 y 4",
    ),
    "economia": (
        "Negocios reabiertos y empleos recuperados por comuna",
        "Cámara de Comercio de Manizales por Caldas (registro mercantil); el DANE (GEIH) "
        "publica desempleo solo para toda la ciudad",
        "9, 4 y etapa 4",
    ),
    "finanzas": (
        "Pérdida estimada, recursos disponibles por fuente y brecha",
        "Secretaría de Hacienda, UNGRD (Fondo Nacional) y aseguradoras",
        "10 y etapas 1 y 2",
    ),
    "estabilizacion": (
        "Recaudo de ICA, ocupación hotelera y café despachado frente a antes del sismo",
        "Secretaría de Hacienda, Cotelco Caldas y Comité de Cafeteros de Caldas",
        "etapa 5",
    ),
}

Inspection = tuple[str, str, str, str | None, datetime]


class _Src:
    """Fuente con versión y corte: toda cifra hereda de aquí su trazabilidad."""

    def __init__(
        self,
        name: str,
        version: int,
        cutoff: datetime,
        simulated: bool = False,
        url: str | None = None,
    ) -> None:
        self.name, self.version, self.cutoff = name, version, cutoff
        self.simulated, self.url = simulated, url

    def fig(
        self,
        key: str,
        label: str,
        value: float | None,
        unit: DashUnit = "conteo",
        target: str | None = None,
        state: FigureState = "neutral",
        note: str | None = None,
    ) -> DashFigure:
        return DashFigure(
            key=key,
            label=label,
            value=value,
            unit=unit,
            source=self.name,
            version=self.version,
            cutoff_at=self.cutoff,
            simulated=self.simulated,
            target=target,
            state=state,
            source_url=self.url,
            note=note,
        )


def _snap_src(snap: LoadedSnapshot, url: str | None = None) -> _Src:
    # La versión de una copia es su número de registros: cambia cuando cambia la fuente.
    return _Src(snap.source, len(snap.records), snap.fetched_at, False, url or snap.query_url)


def _no_data(
    key: str, label: str, unit: DashUnit, source: str, note: str, now: datetime
) -> DashFigure:
    return DashFigure(
        key=key,
        label=label,
        value=None,
        unit=unit,
        source=source,
        version=0,
        cutoff_at=now,
        state="sin_fuente",
        note=note,
    )


def _missing(key: str, label: str, unit: DashUnit, now: datetime) -> DashFigure:
    provider = NO_SOURCE[key][1]
    note = f"Sin fuente conectada: requiere convenio con {provider}."
    return _no_data(f"sin_fuente_{key}", label, unit, provider, note, now)


@lru_cache
def _barrio_comuna() -> dict[str, str]:
    path = get_settings().data_dir / "geo" / "barrios.geojson"
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    return {f["properties"]["name"]: f["properties"]["comuna"] for f in features}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.upper()).encode("ascii", "ignore").decode()


def _latest_by_property(
    rows: list[Inspection], until: datetime | None = None
) -> dict[str, tuple[str, str, str | None]]:
    """Estado vigente de cada predio único (la última evaluación hasta `until`)."""
    latest: dict[str, tuple[str, str, str | None]] = {}
    for prop, color, damage, manzana, at in rows:
        if until is None or at <= until:
            latest[prop] = (color, damage, manzana)
    return latest


def _color_counts(latest: dict[str, tuple[str, str, str | None]]) -> Counter[str]:
    return Counter("colapso" if d == "colapso" else c for c, d, _ in latest.values())


def _habitability(c: Counter[str]) -> float | None:
    return habitability_score(c["verde"], c["amarillo"], c["rojo"] + c["colapso"])


def _families(
    households: list[tuple[Any, int, str | None, datetime]],
    aids: list[tuple[Any, str, datetime]],
    colors: dict[str, str],
    until: datetime | None = None,
) -> tuple[Counter[str], Counter[str], dict[Any, str]]:
    """Situación de vivienda de cada hogar hasta `until` (última ayuda de vivienda manda)."""
    housing: dict[Any, str] = {}
    for hid, aid_type, at in aids:
        if until is None or at <= until:
            housing[hid] = aid_type
    situation: Counter[str] = Counter()
    people: Counter[str] = Counter()
    by_household: dict[Any, str] = {}
    for hid, members, prop, created in households:
        if until is not None and created > until:
            continue
        s = household_situation(housing.get(hid), colors.get(prop or ""))
        situation[s] += 1
        people[s] += members
        by_household[hid] = s
    return situation, people, by_household


@router.get("/dashboard", response_model=RecoveryDashboard)
async def dashboard(
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> RecoveryDashboard:
    """Tablero de recuperación para el COE: 10 indispensables, necesidades y ciclo económico."""
    settings = get_settings()
    now = datetime.now(UTC)
    usgs = load_snapshot("usgs_sismos")
    secop = load_snapshot("secop_sismo_manizales")
    cdiac = load_snapshot("cdiac_lluvia")

    # ------------------------------------------------------------ evento (USGS)
    main_shock = max(usgs.records, key=lambda r: r["magnitude"]) if usgs and usgs.records else None
    event_at = datetime.fromisoformat(main_shock["time"]) if main_shock else None
    day = max((now - event_at).days, 0) if event_at else 0

    # ------------------------------------------------------------ registro de Dacora
    visits = await session.scalar(select(func.count()).select_from(BuildingInspection)) or 0
    registry = _Src(
        "Registro de Dacora (base de datos con bitácora)", int(visits), now, settings.demo_data
    )
    insp: list[Inspection] = [
        (p, str(c), str(d), m, at)
        for p, c, d, m, at in (
            await session.execute(
                select(
                    BuildingInspection.property_id,
                    BuildingInspection.color,
                    BuildingInspection.damage_level,
                    BuildingInspection.manzana_id,
                    BuildingInspection.at,
                ).order_by(BuildingInspection.at, BuildingInspection.created_at)
            )
        ).all()
    ]
    latest = _latest_by_property(insp)
    colors = {p: c for p, (c, _, _) in latest.items()}
    manzana_barrio: dict[str, str] = dict(
        (await session.execute(select(Manzana.id, Manzana.barrio))).all()
    )
    by_barrio: dict[str, Counter[str]] = defaultdict(Counter)
    for color, damage, manzana in latest.values():
        bucket = "colapso" if damage == "colapso" else color
        by_barrio[manzana_barrio.get(manzana or "", "Sin barrio")][bucket] += 1
    city = _color_counts(latest)
    evaluated = len(latest)
    inspected_manzanas = {m for _, _, _, m, _ in insp if m}

    reported_manzanas = {
        m
        for m in (
            await session.execute(
                select(Report.manzana_id)
                .where(
                    Report.category.in_(DAMAGE),
                    Report.status != ReportStatus.descartado,
                    Report.manzana_id.is_not(None),
                )
                .distinct()
            )
        ).scalars()
        if m
    }
    pending_manzanas = reported_manzanas - inspected_manzanas

    service_rows = (
        await session.execute(
            select(Report.barrio, Report.incident_id)
            .where(
                Report.category == Category.servicios_caidos,
                Report.status.not_in(CLOSED_REPORT),
                Report.incident_id.is_not(None),
            )
            .distinct()
        )
    ).all()
    service_by_barrio: dict[str, set[Any]] = defaultdict(set)
    for barrio, incident_id in service_rows:
        service_by_barrio[barrio or "Sin barrio"].add(incident_id)
    service_incidents = len({i for _, i in service_rows})

    # Revisiones a predio (formato GUE-RPD-FR-02): evacuaciones y derivaciones a entidades.
    reviews = (
        await session.execute(
            select(
                PropertyReview.referrals,
                PropertyReview.referrals_done,
                PropertyReview.evacuation_recommended,
            )
        )
    ).all()
    evacuations = sum(1 for _, _, ev in reviews if ev)
    referral_pending: Counter[str] = Counter(
        e for refs, done, _ in reviews for e in refs if e not in done
    )
    from app.routers.recovery_reviews import ENTITY_LABEL

    hh_rows = (
        await session.execute(
            select(
                Household.id,
                Household.members_count,
                Household.property_id,
                Household.created_at,
                Household.rud_status,
                Household.manzana_id,
            )
        )
    ).all()
    households = [(h, int(m), p, c) for h, m, p, c, _, _ in hh_rows]
    aids = [
        (h, str(t), at)
        for h, t, at in (
            await session.execute(
                select(AidDelivery.household_id, AidDelivery.aid_type, AidDelivery.at)
                .where(AidDelivery.aid_type.in_(HOUSING_AID))
                .order_by(AidDelivery.at)
            )
        ).all()
    ]
    situation, situation_people, by_household = _families(households, aids, colors)
    families_by_barrio: dict[str, Counter[str]] = defaultdict(Counter)
    for hid, _m, _p, _c, _r, manzana in hh_rows:
        families_by_barrio[manzana_barrio.get(manzana or "", "Sin barrio")][by_household[hid]] += 1
    families = len(hh_rows)
    people = sum(m for _, m, _, _ in households)
    rud = sum(1 for row in hh_rows if row[4] == "inscrito")
    aided = set((await session.execute(select(AidDelivery.household_id).distinct())).scalars())
    vulnerable = set(
        (
            await session.execute(
                select(HouseholdVulnerability.household_id).where(
                    HouseholdVulnerability.children
                    | HouseholdVulnerability.elderly
                    | HouseholdVulnerability.disability
                    | HouseholdVulnerability.pregnancy
                )
            )
        ).scalars()
    )
    vulnerable_without_aid = len(vulnerable - aided)
    aid_total, aid_dup = (
        await session.execute(
            select(func.count(), func.count().filter(AidDelivery.is_duplicate)).select_from(
                AidDelivery
            )
        )
    ).one()
    shelters = (await session.execute(select(Shelter))).scalars().all()
    shelter_people = sum(s.people for s in shelters)
    full_shelters = [s for s in shelters if s.capacity and s.people / s.capacity >= 0.9]
    shelter_src = _Src(
        "Registro de albergues en Dacora",
        sum(s.version for s in shelters),
        max((s.updated_at for s in shelters), default=now),
        settings.demo_data or any("SIMULADO" in s.source for s in shelters),
    )

    # ------------------------------------------------------------ índice (3 y 7 con datos)
    components: dict[str, float | None] = {
        "habitabilidad": _habitability(city),
        "servicios": None,  # sin fuente conectada
        "familias": pct(situation["casa"], families),
        "economia": None,  # sin fuente conectada
    }
    index = recovery_index(components)

    # Curva: se reconstruye con las fechas del propio registro (sin histórico inventado).
    curve: list[CurvePoint] = []
    if event_at:
        moments = sorted(
            {at for *_, at in insp} | {c for *_, c in households} | {a for *_, a in aids}
        )
        for moment in [*moments, now]:
            if moment < event_at:
                continue
            lat = _latest_by_property(insp, moment)
            sit, _people, _who = _families(
                households, aids, {p: c for p, (c, _, _) in lat.items()}, moment
            )
            value = recovery_index(
                {
                    "habitabilidad": _habitability(_color_counts(lat)),
                    "familias": pct(sit["casa"], sum(sit.values())),
                }
            )
            if value is None:
                continue
            point = CurvePoint(at=moment, day=(moment - event_at).days, value=value)
            if curve and curve[-1].day == point.day:
                curve[-1] = point  # un punto por día: el último del día
            else:
                curve.append(point)

    barrios: list[BarrioRecovery] = []
    for name, comuna in sorted(_barrio_comuna().items()):
        c = by_barrio.get(name, Counter())
        fam = families_by_barrio.get(name, Counter())
        reported = {m for m in reported_manzanas if manzana_barrio.get(m) == name}
        barrios.append(
            BarrioRecovery(
                barrio=name,
                comuna=comuna,
                index=recovery_index(
                    {
                        "habitabilidad": _habitability(c),
                        "familias": pct(fam["casa"], sum(fam.values())),
                    }
                ),
                verde=c["verde"],
                amarillo=c["amarillo"],
                rojo=c["rojo"],
                colapso=c["colapso"],
                damage_reported=len(reported),
                pending=len(reported - inspected_manzanas),
                service_incidents=len(service_by_barrio.get(name, set())),
                families=sum(fam.values()),
            )
        )

    # ------------------------------------------------------------ riesgo activo (5)
    threshold = settings.landslide_rain_threshold_mm_3h
    live_max, live_at = (
        await session.execute(
            select(func.max(RainReading.mm_3h), func.max(RainReading.at)).where(
                RainReading.source == CDIAC_SOURCE,
                RainReading.at >= now - timedelta(minutes=settings.cdiac_max_age_min),
            )
        )
    ).one()
    rain_label = "Lluvia máxima en 3 h (estaciones urbanas)"
    rain_value: float | None = None
    rain_src = _Src(CDIAC_SOURCE, 0, cdiac.fetched_at if cdiac else now)
    if live_max is not None:
        rain_src = _Src(f"{CDIAC_SOURCE} · en vivo", 1, live_at, False, settings.cdiac_base_url)
        rain_value = float(live_max)
    elif cdiac and cdiac.records and now - cdiac.fetched_at <= timedelta(hours=6):
        rain_src = _snap_src(cdiac, settings.cdiac_base_url)
        rain_value = max(float(r["mm_3h"]) for r in cdiac.records)
    if rain_value is not None:
        rain_fig = rain_src.fig(
            "lluvia_3h",
            rain_label,
            rain_value,
            "mm",
            target=f"por debajo del umbral operativo de {threshold:g} mm",
            state="alerta" if rain_value >= threshold else "ok",
        )
    else:
        rain_fig = _no_data(
            "lluvia_3h",
            rain_label,
            "mm",
            CDIAC_SOURCE,
            "Sin lectura reciente del CDIAC: active la fuente CDIAC en Administración "
            "o corra scripts/fetch_sources.py con internet.",
            now,
        )

    quake_figs: list[DashFigure]
    if usgs and main_shock and event_at:
        quake = _snap_src(usgs)
        week = usgs.fetched_at - timedelta(days=7)
        recent = [
            r
            for r in usgs.records
            if r["id"] != main_shock["id"] and datetime.fromisoformat(r["time"]) >= week
        ]
        quake_figs = [
            _Src(quake.name, 1, event_at, False, main_shock["url"]).fig(
                "dias_desde_evento", "Días desde el sismo", day, "dias"
            ),
            quake.fig(
                "sismos_desde_evento",
                "Sismos M ≥ 2,5 a 300 km desde el evento",
                len(usgs.records) - 1,
            ),
            quake.fig("replicas_7d", "Sismos en los 7 días previos al corte", len(recent)),
            quake.fig(
                "replica_max",
                "Magnitud máxima en esos 7 días",
                max((float(r["magnitude"]) for r in recent), default=None),
                "magnitud",
            ),
        ]
    else:
        quake_figs = [
            _no_data(
                "sismicidad",
                "Sismicidad",
                "conteo",
                "USGS / SGC",
                "Sin copia del catálogo sísmico: corra scripts/fetch_sources.py.",
                now,
            )
        ]

    # ------------------------------------------------------------ calidad de reportes (8)
    channels = [
        ChannelCount(channel=str(ch), count=int(n))
        for ch, n in (
            await session.execute(
                select(Report.channel, func.count())
                .group_by(Report.channel)
                .order_by(Report.channel)
            )
        ).all()
    ]
    reports_total = sum(c.count for c in channels)
    incidents = (
        await session.scalar(
            select(func.count()).select_from(Incident).where(Incident.report_count > 0)
        )
        or 0
    )
    critical_queue = (
        await session.scalar(
            select(func.count())
            .select_from(Report)
            .where(
                Report.is_life_threat,
                Report.status.in_((ReportStatus.nuevo, ReportStatus.en_revision)),
            )
        )
        or 0
    )
    engine = _Src("Motor de Dacora", int(reports_total), now, settings.demo_data)
    quality = [
        engine.fig("reports_received", "Reportes recibidos", reports_total),
        engine.fig("incidents_consolidated", "Incidentes consolidados", incidents),
        engine.fig(
            "critical_in_human_queue",
            "Críticos en cola de revisión humana",
            critical_queue,
            state="alerta" if critical_queue else "ok",
        ),
    ]
    targets: tuple[tuple[str, str, DashUnit, str, float, bool], ...] = (
        ("duplicate_detection_rate", "Duplicados detectados", "%", "> 90 %", 90, True),
        ("fake_detection_rate", "Falsos detectados", "%", "> 90 %", 90, True),
        ("critical_auto_discarded", "Críticos descartados por la IA", "conteo", "0", 0, False),
    )
    for key, label, unit, target, limit, above in targets:
        snap = (
            await session.execute(
                select(MetricSnapshot)
                .where(MetricSnapshot.indicator == key)
                .order_by(MetricSnapshot.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snap is None:
            quality.append(
                _no_data(
                    key,
                    label,
                    unit,
                    "evaluate_kpis.py",
                    "Aún no hay medición: corra scripts/evaluate_kpis.py.",
                    now,
                )
            )
            continue
        value = float(snap.value)
        met = value > limit if above else value == limit
        src = _Src(snap.source, snap.version, snap.cutoff_at, settings.demo_data)
        quality.append(src.fig(key, label, value, unit, target, "ok" if met else "alerta"))

    # ------------------------------------------------------------ contratos (SECOP II)
    contracts: list[ContractRow] = []
    contracted = invoiced = paid = first_15 = subsidy = reactivation_value = 0.0
    unpaid = reactivation = 0
    if secop and event_at:
        for r in secop.records:
            value = float(r["valor_del_contrato"])
            signed = (
                date.fromisoformat(str(r["fecha_de_firma"])[:10]) if r["fecha_de_firma"] else None
            )
            contracted += value
            invoiced += float(r["valor_facturado"])
            paid += float(r["valor_pagado"])
            unpaid += float(r["valor_pagado"]) == 0
            if signed and (signed - event_at.date()).days <= 15:
                first_15 += value
            objeto = _norm(str(r["objeto_del_contrato"]))
            if "ARRENDAMIENTO" in objeto or "ALOJAMIENTO TEMPORAL" in objeto:
                subsidy += value
            if "REACTIVACION" in objeto:
                reactivation += 1
                reactivation_value += value
            contracts.append(
                ContractRow(
                    id=str(r["id_contrato"]),
                    entity=str(r["nombre_entidad"]),
                    signed_at=signed,
                    status=str(r["estado_contrato"]),
                    object=str(r["objeto_del_contrato"]),
                    value_cop=value,
                    invoiced_cop=float(r["valor_facturado"]),
                    paid_cop=float(r["valor_pagado"]),
                    url=r.get("urlproceso"),
                )
            )
        contracts.sort(key=lambda c: c.value_cop, reverse=True)
    paid_pct = pct(paid, contracted)
    secop_src = _snap_src(secop) if secop else None

    def secop_fig(
        key: str,
        label: str,
        value: float | None,
        unit: DashUnit = "cop",
        state: FigureState = "neutral",
    ) -> DashFigure:
        if secop_src is None:
            note = "Sin copia de SECOP II: corra scripts/fetch_sources.py."
            return _no_data(key, label, unit, "SECOP II · datos.gov.co", note, now)
        return secop_src.fig(key, label, value, unit, state=state)

    # ------------------------------------------------------------ indicadores
    indicators = [
        Indicator(
            number=1,
            key="familias_damnificadas",
            title="Familias damnificadas únicas",
            block="encabezado",
            source="Censo único de Dacora · exportable RUD (UNGRD)",
            figures=[
                registry.fig("familias_unicas", "Familias únicas (HMAC)", families),
                registry.fig("personas_damnificadas", "Personas damnificadas", people),
                registry.fig("rud_inscritos", "Inscritas en el RUD", rud),
            ],
        ),
        Indicator(
            number=2,
            key="predios_evaluados",
            title="Predios evaluados únicos contra pendientes",
            block="encabezado",
            source="Inspectores y reportes ciudadanos en Dacora",
            figures=[
                registry.fig("predios_evaluados", "Predios evaluados únicos", evaluated),
                registry.fig(
                    "manzanas_dano_reportado", "Manzanas con daño reportado", len(reported_manzanas)
                ),
                registry.fig(
                    "manzanas_sin_evaluar",
                    "De ellas, sin ninguna evaluación",
                    len(pending_manzanas),
                    state="alerta" if pending_manzanas else "ok",
                ),
                registry.fig(
                    "visitas_repetidas_evitadas",
                    "Visitas repetidas unidas a su predio",
                    max(visits - evaluated, 0),
                ),
                registry.fig("formatos_revision", "Formatos de revisión a predio", len(reviews)),
                registry.fig(
                    "evacuaciones_recomendadas",
                    "Con evacuación recomendada",
                    evacuations,
                    state="alerta" if evacuations else "neutral",
                ),
            ],
        ),
        Indicator(
            number=3,
            key="semaforo_nsr10",
            title="Viviendas por semáforo NSR-10",
            block="encabezado",
            source="EDAN en Dacora",
            figures=[
                registry.fig("predios_verde", "Verde · habitable", city["verde"]),
                registry.fig("predios_amarillo", "Amarillo · uso restringido", city["amarillo"]),
                registry.fig("predios_rojo", "Rojo · no habitable", city["rojo"]),
                registry.fig("predios_colapso", "Colapsado", city["colapso"]),
            ],
        ),
        Indicator(
            number=4,
            key="indice_recuperacion",
            title="Índice de recuperación",
            block="encabezado",
            source="Calculado por Dacora con los componentes que tienen fuente (3 y 7)",
            figures=[
                registry.fig("indice_recuperacion", "Índice de la ciudad", index, "%"),
                registry.fig(
                    "barrios_bajo_50",
                    "Barrios por debajo de 50 %",
                    sum(1 for b in barrios if b.index is not None and b.index < 50),
                ),
            ],
        ),
        Indicator(
            number=5,
            key="riesgo_activo",
            title="Días desde el evento y riesgo activo",
            block="encabezado",
            source="USGS (catálogo sísmico) y CDIAC/SIMAC (lluvia)",
            figures=[*quake_figs, rain_fig],
        ),
        Indicator(
            number=6,
            key="servicios_basicos",
            title="Servicios básicos",
            block="operacion",
            source="Reportes ciudadanos en Dacora; cobertura: empresas de servicios",
            figures=[
                registry.fig(
                    "incidentes_servicios",
                    "Incidentes abiertos de servicios caídos",
                    service_incidents,
                    state="alerta" if service_incidents else "ok",
                ),
                registry.fig(
                    "barrios_servicios",
                    "Barrios con servicios caídos reportados",
                    sum(1 for b in barrios if b.service_incidents),
                ),
                registry.fig(
                    "derivaciones_pendientes",
                    "Visitas de entidades pendientes (formato, sección 6)",
                    sum(referral_pending.values()),
                    state="alerta" if referral_pending else "ok",
                ),
                _missing("servicios", "Cobertura de servicios por barrio", "%", now),
            ],
        ),
        Indicator(
            number=7,
            key="familias_situacion",
            title="Familias por situación y ayudas",
            block="operacion",
            source="Censo y ayudas en Dacora",
            figures=[
                registry.fig("familias_albergue", "En albergue", situation["albergue"]),
                registry.fig("familias_arriendo", "En arriendo temporal", situation["arriendo"]),
                registry.fig("familias_casa", "En casa", situation["casa"]),
                registry.fig(
                    "familias_sin_solucion",
                    "Predio rojo sin solución de vivienda",
                    situation["sin_solucion"],
                    state="alerta" if situation["sin_solucion"] else "ok",
                ),
                registry.fig("ayudas_entregadas", "Ayudas entregadas", aid_total),
                registry.fig("ayudas_repetidas", "Repetidas con justificación", aid_dup),
                shelter_src.fig("personas_albergue", "Personas en albergues", shelter_people),
            ],
        ),
        Indicator(
            number=8,
            key="calidad_reportes",
            title="Calidad de los reportes",
            block="operacion",
            source="Motor de Dacora y evaluate_kpis.py",
            figures=quality,
        ),
        Indicator(
            number=9,
            key="negocios_empleo",
            title="Negocios reabiertos y empleos recuperados",
            block="economia",
            source="Contratos: SECOP II; negocios y empleo: Cámara de Comercio y DANE",
            figures=[
                secop_fig(
                    "contratos_reactivacion",
                    "Contratos de reactivación económica",
                    reactivation,
                    "conteo",
                ),
                secop_fig("valor_reactivacion", "Valor de esos contratos", reactivation_value),
                _missing("economia", "Negocios reabiertos y empleos recuperados", "conteo", now),
            ],
        ),
        Indicator(
            number=10,
            key="recursos_trazabilidad",
            title="Recursos y trazabilidad",
            block="economia",
            source="Contratos: SECOP II; presupuesto: Hacienda y UNGRD (sin convenio)",
            figures=[
                secop_fig(
                    "contratos_sismo", "Contratos ligados al sismo", len(contracts), "conteo"
                ),
                secop_fig("contratado", "Valor contratado", contracted),
                secop_fig("facturado", "Valor facturado", invoiced),
                secop_fig("pagado", "Pagos registrados en SECOP", paid),
                secop_fig(
                    "pagado_pct",
                    "Pagado sobre lo contratado",
                    paid_pct,
                    "%",
                    state="alerta" if paid_pct is not None and paid_pct < 10 else "neutral",
                ),
                _missing("finanzas", "Pérdida estimada, recursos disponibles y brecha", "cop", now),
            ],
        ),
    ]

    # ------------------------------------------------------------ ciclo económico (parte B)
    event_fig = (
        _Src("USGS · servicio FDSN", 1, event_at, False, main_shock["url"]).fig(
            "magnitud_evento", "Magnitud del sismo principal", main_shock["magnitude"], "magnitud"
        )
        if main_shock and event_at
        else quake_figs[0]
    )
    progress: list[tuple[float | None, str | None]] = [
        (
            (len(reported_manzanas) - len(pending_manzanas)) / len(reported_manzanas)
            if reported_manzanas
            else None,
            "manzanas con daño reportado que ya tienen evaluación",
        ),
        (None, None),
        (
            paid / contracted if contracted else None,
            "pagos registrados en SECOP ÷ valor contratado",
        ),
        (None, None),
        (None, None),
    ]
    stage_figures = [
        [
            event_fig,
            registry.fig(
                "predios_rojo_colapso",
                "Predios rojos o colapsados",
                city["rojo"] + city["colapso"],
            ),
            registry.fig(
                "manzanas_dano_reportado", "Manzanas con daño reportado", len(reported_manzanas)
            ),
            _missing("finanzas", "Pérdida estimada", "cop", now),
            _missing("economia", "Negocios cerrados y empleos detenidos", "conteo", now),
        ],
        [
            secop_fig("contratado_15d", "Contratado en los primeros 15 días", first_15),
            _missing("finanzas", "Recursos disponibles por fuente y brecha", "cop", now),
        ],
        [
            secop_fig("contratado", "Valor contratado", contracted),
            secop_fig("facturado", "Valor facturado", invoiced),
            secop_fig("pagado", "Pagos registrados en SECOP", paid),
            secop_fig("subsidios_arriendo", "Contratado en subsidios de arriendo", subsidy),
            registry.fig("ayudas_entregadas", "Ayudas entregadas a hogares", aid_total),
        ],
        [
            secop_fig(
                "contratos_reactivacion",
                "Contratos de reactivación económica",
                reactivation,
                "conteo",
            ),
            _missing("economia", "Negocios reabiertos y empleos recuperados", "conteo", now),
        ],
        [_missing("estabilizacion", "Recaudo de ICA, turismo y café frente a antes", "%", now)],
    ]
    stages = [
        Stage(
            number=w.number,
            title=w.title,
            question=w.question,
            start_day=w.start_day,
            end_day=w.end_day,
            status=stage_status(day, w, p),
            progress_pct=round(100 * min(p, 1.0), 1) if p is not None else None,
            progress_basis=basis,
            figures=f,
        )
        for w, (p, basis), f in zip(STAGES, progress, stage_figures, strict=True)
    ]

    # ------------------------------------------------------------ necesidades
    needs: list[Need] = []
    if critical_queue:
        needs.append(
            Need(
                key="criticos_en_cola",
                title="Reportes con riesgo vital esperan revisión humana",
                detail="Ninguno se descarta solo: revíselos en el tablero PMU.",
                severity="critica",
                value=critical_queue,
            )
        )
    if rain_value is not None and rain_value >= threshold:
        needs.append(
            Need(
                key="lluvia_umbral",
                title="Lluvia sobre el umbral operativo de deslizamiento",
                detail=(
                    f"{rain_value:g} mm en 3 h según {rain_src.name} (umbral {threshold:g} mm): "
                    "revise laderas con predios rojos."
                ),
                severity="critica",
                value=round(rain_value),
            )
        )
    if situation["sin_solucion"]:
        needs.append(
            Need(
                key="familias_sin_solucion",
                title="Familias en predio rojo sin solución de vivienda",
                detail=(
                    f"{situation_people['sin_solucion']} personas: "
                    "asignar albergue o subsidio de arriendo."
                ),
                severity="critica",
                value=situation["sin_solucion"],
            )
        )
    if vulnerable_without_aid:
        needs.append(
            Need(
                key="vulnerables_sin_ayuda",
                title="Hogares con niñez, adultos mayores, discapacidad o gestación sin ayuda",
                detail="Priorizar la primera entrega (dato sensible: solo PMU/COE).",
                severity="alta",
                value=vulnerable_without_aid,
            )
        )
    if pending_manzanas:
        worst = [b for b in sorted(barrios, key=lambda b: b.pending, reverse=True)[:3] if b.pending]
        needs.append(
            Need(
                key="manzanas_sin_evaluar",
                title="Manzanas con daño reportado y ninguna evaluación de habitabilidad",
                detail="Más pendientes: " + ", ".join(f"{b.barrio} ({b.pending})" for b in worst),
                severity="alta",
                value=len(pending_manzanas),
            )
        )
    if referral_pending:
        top = ", ".join(
            f"{ENTITY_LABEL.get(e, e)} ({n})"  # type: ignore[call-overload]
            for e, n in referral_pending.most_common(3)
        )
        needs.append(
            Need(
                key="derivaciones_pendientes",
                title="Predios revisados que esperan la visita de una entidad",
                detail=f"Más pendientes: {top}.",
                severity="alta",
                value=sum(referral_pending.values()),
            )
        )
    if full_shelters:
        needs.append(
            Need(
                key="albergues_llenos",
                title="Albergues al 90 % o más de su capacidad",
                detail=", ".join(s.name for s in full_shelters),
                severity="alta",
                value=len(full_shelters),
            )
        )
    if service_incidents:
        worst_services = [
            b
            for b in sorted(barrios, key=lambda b: b.service_incidents, reverse=True)[:3]
            if b.service_incidents
        ]
        needs.append(
            Need(
                key="servicios_caidos",
                title="Incidentes de servicios caídos sin atender",
                detail="Más afectados: "
                + ", ".join(f"{b.barrio} ({b.service_incidents})" for b in worst_services),
                severity="media",
                value=service_incidents,
            )
        )
    if contracts and paid_pct is not None and paid_pct < 10:
        needs.append(
            Need(
                key="pagos_sin_registro",
                title="Contratos del sismo sin pagos registrados en SECOP II",
                detail=(
                    f"{unpaid} de {len(contracts)} contratos no reportan pagos; "
                    "verificar con Hacienda si falta el pago o su registro (Ley 1712)."
                ),
                severity="media",
                value=unpaid,
            )
        )

    # ------------------------------------------------------------ respaldo de las fuentes
    def info(
        key: str, snap: LoadedSnapshot | None, title: str, source: str, feeds: str
    ) -> SourceInfo:
        if snap is None:
            return SourceInfo(key=key, title=title, source=source, status="sin_copia", feeds=feeds)
        return SourceInfo(
            key=key,
            title=snap.title,
            source=snap.source,
            status="conectada",
            query_url=snap.query_url,
            license=snap.license,
            attribution=snap.attribution,
            fetched_at=snap.fetched_at,
            record_count=len(snap.records),
            sha256=snap.sha256,
            verified=snap.verified,
            feeds=feeds,
        )

    cdiac_info = (
        SourceInfo(
            key="cdiac",
            title="Lluvia por estación urbana (en vivo)",
            source=CDIAC_SOURCE,
            status="conectada",
            query_url=settings.cdiac_base_url,
            fetched_at=live_at,
            feeds="5",
        )
        if live_max is not None
        else info("cdiac", cdiac, "Lluvia por estación urbana", CDIAC_SOURCE, "5")
    )
    sources = [
        SourceInfo(
            key="dacora",
            title="Censo, inspecciones, ayudas, albergues y reportes",
            source="Registro de Dacora (PostgreSQL, solo-agregar con bitácora)",
            status="conectada",
            fetched_at=now,
            attribution="Datos de demostración (Ley 1581)" if settings.demo_data else None,
            feeds="1, 2, 3, 4, 6, 7, 8 y etapas 1 y 3",
        ),
        info("usgs", usgs, "Catálogo sísmico", "USGS · servicio FDSN", "5 y etapa 1"),
        info(
            "secop", secop, "Contratos del sismo", "SECOP II · datos.gov.co", "9, 10, etapas 2 a 4"
        ),
        cdiac_info,
        *[
            SourceInfo(key=k, title=title, source=provider, status="sin_convenio", feeds=feeds)
            for k, (title, provider, feeds) in NO_SOURCE.items()
        ],
    ]

    return RecoveryDashboard(
        cutoff_at=now,
        event_at=event_at,
        event_label=f"M {main_shock['magnitude']} · {main_shock['place']}" if main_shock else None,
        event_url=main_shock["url"] if main_shock else None,
        day=day,
        index=index,
        index_components=components,
        needs=needs,
        indicators=indicators,
        barrios=barrios,
        index_curve=curve,
        channels=channels,
        contracts=contracts[:12],
        sources=sources,
        stages=stages,
    )
