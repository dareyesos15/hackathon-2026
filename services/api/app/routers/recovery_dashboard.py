"""Tablero de recuperación unificado: los 10 indispensables y el ciclo económico.

Regla de oro: cada cifra lleva su nombre del diccionario de indicadores, fuente, versión y hora
de corte, y se cuentan predios únicos, no visitas. Lo que Dacora registra (habitabilidad, censo,
ayudas, albergues, reportes) se calcula en vivo; las fuentes externas llegan SIMULADAS desde
`recovery_context.json` (ver app/core/recovery_dashboard.py).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.core import cascade
from app.core.recovery_dashboard import (
    SERVICES,
    STAGES,
    habitability_score,
    household_situation,
    load_context,
    pct,
    recovery_index,
    services_score,
    stage_status,
)
from app.db import get_session
from app.domain import AidType, ReportStatus, Role
from app.models import (
    AidDelivery,
    BuildingInspection,
    Household,
    HouseholdVulnerability,
    Incident,
    Manzana,
    MetricSnapshot,
    Report,
    Shelter,
)
from app.recovery_schemas import (
    BarrioRecovery,
    ChannelCount,
    CurvePoint,
    DashFigure,
    DashUnit,
    EconomyRow,
    FigureState,
    FundingSource,
    Indicator,
    Need,
    RecoveryDashboard,
    Stage,
)

router = APIRouter(prefix="/recovery", tags=["recuperación"])

DACORA = "Dacora · registro en vivo"
HOUSING_AID = (AidType.albergue, AidType.subsidio_arriendo)


class _Src:
    """Fuente con versión y corte: toda cifra hereda de aquí su trazabilidad."""

    def __init__(self, name: str, version: int, cutoff: datetime, simulated: bool) -> None:
        self.name, self.version, self.cutoff, self.simulated = name, version, cutoff, simulated

    def fig(
        self,
        key: str,
        label: str,
        value: float | None,
        unit: DashUnit = "conteo",
        target: str | None = None,
        state: FigureState = "neutral",
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
        )


def _ext(ctx: dict[str, Any], key: str) -> _Src:
    s = ctx["sources"][key]
    return _Src(s["name"], int(s["version"]), datetime.fromisoformat(s["cutoff_at"]), True)


async def _latest_inspections(session: AsyncSession) -> list[tuple[str, str, str, str | None]]:
    """Estado vigente por predio único: (property_id, color, daño, barrio)."""
    ranked = select(
        BuildingInspection.property_id,
        BuildingInspection.color,
        BuildingInspection.damage_level,
        BuildingInspection.manzana_id,
        func.row_number()
        .over(
            partition_by=BuildingInspection.property_id,
            order_by=(BuildingInspection.at.desc(), BuildingInspection.created_at.desc()),
        )
        .label("rn"),
    ).subquery()
    rows = await session.execute(
        select(ranked.c.property_id, ranked.c.color, ranked.c.damage_level, Manzana.barrio)
        .outerjoin(Manzana, Manzana.id == ranked.c.manzana_id)
        .where(ranked.c.rn == 1)
    )
    return [(p, str(c), str(d), b) for p, c, d, b in rows.all()]


async def _snapshot(session: AsyncSession, indicator: str) -> MetricSnapshot | None:
    return (
        await session.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.indicator == indicator)
            .order_by(MetricSnapshot.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.get("/dashboard", response_model=RecoveryDashboard)
async def dashboard(
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> RecoveryDashboard:
    """Tablero de recuperación para el COE: 10 indispensables, necesidades y ciclo económico."""
    ctx = load_context()
    now = datetime.now(UTC)
    event_at = datetime.fromisoformat(ctx["event"]["at"])
    day = max((now - event_at).days, 0)
    visits = await session.scalar(select(func.count()).select_from(BuildingInspection)) or 0
    live = _Src(DACORA, int(visits), now, True)

    # ------------------------------------------------------------ predios (indicadores 2 y 3)
    props = await _latest_inspections(session)
    color_by_property = {p: c for p, c, _, _ in props}
    by_barrio: dict[str, Counter[str]] = defaultdict(Counter)
    for _p, color, damage, barrio in props:
        bucket = "colapso" if damage == "colapso" else color
        by_barrio[barrio or "Sin barrio"][bucket] += 1
    city = Counter[str]()
    for c in by_barrio.values():
        city.update(c)
    requested = {b: int(n) for b, n in ctx["visit_requests"].items()}
    evaluated = len(props)
    pending = sum(max(requested[b] - sum(by_barrio[b].values()), 0) for b in requested)

    # ------------------------------------------------------------ hogares (indicadores 1 y 7)
    hh_rows = (
        await session.execute(
            select(
                Household.id,
                Household.members_count,
                Household.property_id,
                Household.rud_status,
                Manzana.barrio,
            ).outerjoin(Manzana, Manzana.id == Household.manzana_id)
        )
    ).all()
    housing = dict(
        (
            await session.execute(
                select(AidDelivery.household_id, AidDelivery.aid_type)
                .where(AidDelivery.aid_type.in_(HOUSING_AID))
                .order_by(AidDelivery.household_id, AidDelivery.at)
            )
        ).all()
    )  # la última entrega de vivienda de cada hogar queda como valor
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
    situation: Counter[str] = Counter()
    situation_people: Counter[str] = Counter()
    families_by_barrio: dict[str, Counter[str]] = defaultdict(Counter)
    people = rud = 0
    for hid, members, property_id, rud_status, barrio in hh_rows:
        aid = housing.get(hid)
        s = household_situation(str(aid) if aid else None, color_by_property.get(property_id or ""))
        situation[s] += 1
        situation_people[s] += members
        families_by_barrio[barrio or "Sin barrio"][s] += 1
        people += members
        rud += rud_status == "inscrito"
    families = len(hh_rows)
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

    # ------------------------------------------------------------ servicios y economía
    services: dict[str, dict[str, Any]] = ctx["services"]
    economy: dict[str, dict[str, int]] = ctx["economy"]
    city_services = {
        s: round(sum(float(r[s]) for r in services.values()) / len(services), 1) for s in SERVICES
    }
    closed = sum(e["businesses_closed"] for e in economy.values())
    reopened = sum(e["businesses_reopened"] for e in economy.values())
    jobs_lost = sum(e["jobs_lost"] for e in economy.values())
    jobs_back = sum(e["jobs_recovered"] for e in economy.values())

    # ------------------------------------------------------------ índice (3, 6, 7, 9)
    components: dict[str, float | None] = {
        "habitabilidad": habitability_score(
            city["verde"], city["amarillo"], city["rojo"] + city["colapso"]
        ),
        "servicios": round(sum(city_services.values()) / len(SERVICES), 1),
        "familias": pct(situation["casa"], families),
        "economia": pct(reopened, closed),
    }
    index = recovery_index(components)

    barrio_comuna = dict(
        (await session.execute(select(Manzana.barrio, Manzana.comuna).distinct())).all()
    )
    barrios: list[BarrioRecovery] = []
    for name in sorted(requested):
        c = by_barrio.get(name, Counter())
        fam = families_by_barrio.get(name, Counter())
        comuna = barrio_comuna.get(name, "")
        eco = economy.get(comuna)
        row = services.get(name)
        barrios.append(
            BarrioRecovery(
                barrio=name,
                comuna=comuna,
                index=recovery_index(
                    {
                        "habitabilidad": habitability_score(
                            c["verde"], c["amarillo"], c["rojo"] + c["colapso"]
                        ),
                        "servicios": services_score(row),
                        "familias": pct(fam["casa"], sum(fam.values())),
                        "economia": pct(eco["businesses_reopened"], eco["businesses_closed"])
                        if eco
                        else None,
                    }
                ),
                verde=c["verde"],
                amarillo=c["amarillo"],
                rojo=c["rojo"],
                colapso=c["colapso"],
                requested=requested[name],
                pending=max(requested[name] - sum(c.values()), 0),
                services={s: int(row[s]) for s in SERVICES} if row else {},
                services_eta=date.fromisoformat(row["eta"]) if row else None,
                families=sum(fam.values()),
            )
        )

    history = [
        CurvePoint(day=int(p["day"]), value=float(p["value"]), simulated=True)
        for p in ctx["index_history"]
        if int(p["day"]) < day
    ]
    curve = history + (
        [CurvePoint(day=day, value=index, simulated=False)] if index is not None else []
    )

    # ------------------------------------------------------------ riesgo activo (5)
    sgc = _ext(ctx, "sgc")
    rain_src = _ext(ctx, "lluvia")
    reading = await cascade.latest_rain(session)
    rain_mm = float(reading.mm_3h) if reading else float(ctx["rain"]["mm_3h"])
    if reading:
        rain_src = _Src(f"{reading.station_code} ({reading.source})", 1, reading.at, True)
    threshold = float(ctx["rain"]["threshold_mm_3h"])
    shocks = ctx["aftershocks"]
    max_mag = max((float(a["magnitude"]) for a in shocks), default=None)

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
    engine = _Src("Motor de Dacora", int(reports_total), now, True)
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
        # (indicador, nombre, unidad, meta, umbral, True = mayor que umbral; False = igual)
        ("duplicate_detection_rate", "Duplicados detectados", "%", "> 90 %", 90, True),
        ("fake_detection_rate", "Falsos detectados", "%", "> 90 %", 90, True),
        ("critical_auto_discarded", "Críticos descartados por la IA", "conteo", "0", 0, False),
    )
    for key, label, unit, target, limit, above in targets:
        snap = await _snapshot(session, key)
        value = float(snap.value) if snap else None
        src = (
            _Src(snap.source, snap.version, snap.cutoff_at, True)
            if snap
            else _Src("evaluate_kpis.py (sin corrida)", 0, now, True)
        )
        met = value is not None and (value > limit if above else value == limit)
        state: FigureState = "neutral" if value is None else ("ok" if met else "alerta")
        quality.append(src.fig(key, label, value, unit, target, state))

    # ------------------------------------------------------------ finanzas (10)
    fin = ctx["finance"]
    money = _ext(ctx, "finanzas")
    available = float(sum(s["amount_cop"] for s in fin["funding_sources"]))
    loss = float(fin["estimated_loss_cop"])
    funnel = fin["funnel"]

    alcaldia = _ext(ctx, "alcaldia")
    svc = _ext(ctx, "servicios")
    eco_src = _ext(ctx, "economia")
    indicators = [
        Indicator(
            number=1,
            key="familias_damnificadas",
            title="Familias damnificadas únicas",
            block="encabezado",
            source="Censo único de Dacora · exportable RUD (UNGRD)",
            figures=[
                live.fig("familias_unicas", "Familias únicas (HMAC)", families),
                live.fig("personas_damnificadas", "Personas damnificadas", people),
                live.fig("rud_inscritos", "Inscritas en el RUD", rud),
            ],
        ),
        Indicator(
            number=2,
            key="predios_evaluados",
            title="Predios evaluados únicos contra pendientes",
            block="encabezado",
            source="Inspectores en Dacora · solicitudes de la Alcaldía · catastro IGAC",
            figures=[
                live.fig("predios_evaluados", "Predios evaluados únicos", evaluated),
                alcaldia.fig(
                    "predios_pendientes",
                    "Predios pendientes de visita",
                    pending,
                    state="alerta" if pending else "ok",
                ),
                live.fig(
                    "visitas_repetidas_evitadas",
                    "Visitas repetidas unidas a su predio",
                    max(visits - evaluated, 0),
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
                live.fig("predios_verde", "Verde · habitable", city["verde"]),
                live.fig("predios_amarillo", "Amarillo · uso restringido", city["amarillo"]),
                live.fig("predios_rojo", "Rojo · no habitable", city["rojo"]),
                live.fig("predios_colapso", "Colapsado", city["colapso"]),
            ],
        ),
        Indicator(
            number=4,
            key="indice_recuperacion",
            title="Índice de recuperación",
            block="encabezado",
            source="Calculado por Dacora (indicadores 3, 6, 7 y 9)",
            figures=[
                live.fig("indice_recuperacion", "Índice de la ciudad", index, "%"),
                live.fig(
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
            source="SGC, estaciones de la UNAL y Corpocaldas",
            figures=[
                live.fig("dias_desde_evento", "Días desde el sismo", day, "dias"),
                sgc.fig("replicas_7d", "Réplicas en 7 días", len(shocks)),
                sgc.fig("replica_max", "Magnitud máxima", max_mag, "magnitud"),
                rain_src.fig(
                    "lluvia_3h",
                    "Lluvia en 3 h",
                    rain_mm,
                    "mm",
                    target=f"umbral {threshold:g} mm",
                    state="alerta" if rain_mm >= threshold else "ok",
                ),
            ],
        ),
        Indicator(
            number=6,
            key="servicios_basicos",
            title="Servicios básicos",
            block="operacion",
            source="Aguas de Manizales, CHEC, Efigas y Obras Públicas",
            figures=[
                svc.fig(f"servicio_{s}", label, city_services[s], "%")
                for s, label in (
                    ("agua", "Agua"),
                    ("energia", "Energía"),
                    ("gas", "Gas"),
                    ("telecom", "Telecomunicaciones"),
                    ("vias", "Vías"),
                )
            ],
        ),
        Indicator(
            number=7,
            key="familias_situacion",
            title="Familias por situación y ayudas",
            block="operacion",
            source="UGR, Cruz Roja y Dacora",
            figures=[
                live.fig("familias_albergue", "En albergue", situation["albergue"]),
                live.fig("familias_arriendo", "En arriendo temporal", situation["arriendo"]),
                live.fig("familias_casa", "En casa", situation["casa"]),
                live.fig(
                    "familias_sin_solucion",
                    "Predio rojo sin solución de vivienda",
                    situation["sin_solucion"],
                    state="alerta" if situation["sin_solucion"] else "ok",
                ),
                live.fig("ayudas_entregadas", "Ayudas entregadas", aid_total),
                live.fig("ayudas_repetidas", "Repetidas con justificación", aid_dup),
                live.fig("personas_albergue", "Personas en albergues", shelter_people),
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
            source="Cámara de Comercio, DANE y Dacora",
            figures=[
                eco_src.fig("negocios_reabiertos", "Negocios reabiertos", reopened),
                eco_src.fig("negocios_cerrados", "Negocios cerrados por el sismo", closed),
                eco_src.fig("empleos_recuperados", "Empleos recuperados", jobs_back),
                eco_src.fig("empleos_perdidos", "Empleos detenidos", jobs_lost),
            ],
        ),
        Indicator(
            number=10,
            key="recursos_trazabilidad",
            title="Recursos y trazabilidad",
            block="economia",
            source="Hacienda, UNGRD, SECOP y aseguradoras",
            figures=[
                money.fig("perdida_estimada", "Pérdida estimada", loss, "cop"),
                money.fig("recursos_disponibles", "Recursos por fuente", available, "cop"),
                money.fig(
                    "brecha",
                    "Brecha",
                    max(loss - available, 0),
                    "cop",
                    state="alerta" if loss > available else "ok",
                ),
                money.fig("comprometido", "Comprometido", funnel["committed_cop"], "cop"),
                money.fig("contratado", "Contratado", funnel["contracted_cop"], "cop"),
                money.fig("pagado", "Pagado", funnel["paid_cop"], "cop"),
                money.fig("verificado", "Resultado verificado", funnel["verified_cop"], "cop"),
                money.fig("dias_pago", "Días promedio de pago", fin["avg_days_to_payment"], "dias"),
            ],
        ),
    ]

    # ------------------------------------------------------------ ciclo económico (parte B)
    stab = ctx["stabilization"]
    stab_src = _ext(ctx, "estabilizacion")
    benefits = fin["benefits"]
    total_requested = sum(requested.values())
    progress = [
        evaluated / total_requested if total_requested else None,
        available / loss if loss else None,
        benefits["paid"] / benefits["approved"] if benefits["approved"] else None,
        reopened / closed if closed else None,
        (stab["ica_vs_pre_pct"] + stab["tourism_vs_pre_pct"] + stab["coffee_vs_pre_pct"]) / 300,
    ]
    stage_figures = [
        [
            money.fig("perdida_estimada", "Pérdida estimada", loss, "cop"),
            eco_src.fig("negocios_cerrados", "Negocios cerrados", closed),
            eco_src.fig("empleos_perdidos", "Empleos detenidos", jobs_lost),
            eco_src.fig(
                "zonas_comerciales",
                "Zonas comerciales afectadas",
                ctx["impact"]["commercial_zones_affected"],
            ),
            live.fig(
                "predios_rojo_colapso", "Predios rojos o colapsados", city["rojo"] + city["colapso"]
            ),
        ],
        [
            *[
                money.fig(f"fuente_{i}", s["name"], s["amount_cop"], "cop")
                for i, s in enumerate(fin["funding_sources"])
            ],
            money.fig("brecha", "Brecha", max(loss - available, 0), "cop"),
        ],
        [
            money.fig("beneficios_solicitados", "Solicitados", benefits["requested"]),
            money.fig("beneficios_aprobados", "Aprobados", benefits["approved"]),
            money.fig("beneficios_pagados", "Pagados", benefits["paid"]),
            money.fig("dias_pago", "Días hasta el pago", fin["avg_days_to_payment"], "dias"),
            money.fig(
                "dobles_bloqueados", "Dobles beneficios bloqueados", fin["double_benefits_blocked"]
            ),
        ],
        [
            eco_src.fig("negocios_reabiertos", "Negocios reabiertos", reopened),
            eco_src.fig("empleos_recuperados", "Empleos recuperados", jobs_back),
            money.fig(
                "compras_locales", "Compras locales (SECOP)", fin["local_purchases_cop"], "cop"
            ),
        ],
        [
            stab_src.fig("ica", "Recaudo ICA vs. antes", stab["ica_vs_pre_pct"], "%"),
            stab_src.fig("turismo", "Turismo vs. antes", stab["tourism_vs_pre_pct"], "%"),
            stab_src.fig("cafe", "Café despachado vs. antes", stab["coffee_vs_pre_pct"], "%"),
        ],
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
            figures=f,
        )
        for w, p, f in zip(STAGES, progress, stage_figures, strict=True)
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
    if rain_mm >= threshold:
        needs.append(
            Need(
                key="lluvia_umbral",
                title="Lluvia sobre el umbral de deslizamiento",
                detail=(
                    f"{rain_mm:g} mm en 3 h (umbral {threshold:g} mm): "
                    "revise laderas con predios rojos."
                ),
                severity="critica",
                value=round(rain_mm),
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
    if pending:
        worst = sorted(barrios, key=lambda b: b.pending, reverse=True)[:3]
        needs.append(
            Need(
                key="predios_pendientes",
                title="Predios con solicitud de visita sin evaluar",
                detail="Más pendientes: " + ", ".join(f"{b.barrio} ({b.pending})" for b in worst),
                severity="alta",
                value=pending,
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
    lagging = sorted(
        ((b.barrio, s, v) for b in barrios for s, v in b.services.items() if v < 80),
        key=lambda t: t[2],
    )
    if lagging:
        names = {
            "agua": "agua",
            "energia": "energía",
            "gas": "gas",
            "telecom": "telecom",
            "vias": "vías",
        }
        needs.append(
            Need(
                key="servicios_rezagados",
                title="Barrios con un servicio básico por debajo de 80 %",
                detail="Más rezagados: "
                + ", ".join(f"{b} · {names[s]} {v} %" for b, s, v in lagging[:3]),
                severity="media",
                value=len({b for b, _, _ in lagging}),
            )
        )
    if loss > available:
        needs.append(
            Need(
                key="brecha_financiera",
                title="Brecha entre pérdida estimada y recursos disponibles",
                detail=f"Faltan {round((loss - available) / 1e9):,} mil millones de pesos.".replace(
                    ",", "."
                ),
                severity="media",
                value=round((loss - available) / 1e9),
            )
        )

    return RecoveryDashboard(
        cutoff_at=now,
        event_at=event_at,
        day=day,
        index=index,
        index_components=components,
        needs=needs,
        indicators=indicators,
        barrios=barrios,
        index_curve=curve,
        channels=channels,
        economy=[EconomyRow(comuna=k, **v) for k, v in sorted(economy.items())],
        funding=[FundingSource(**s) for s in fin["funding_sources"]],
        stages=stages,
    )
