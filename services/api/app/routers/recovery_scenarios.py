"""Escenarios SIMULADOS del tablero de recuperación (mejor y peor caso de acceso a datos).

- `GET /recovery/scenarios`: estadísticas Monte Carlo de la confianza que tendría Dacora en cada
  escenario (media e IC del 90 %).
- `GET /recovery/dashboard?scenario=mejor|peor` (en recovery_dashboard.py) usa
  `scenario_dashboard()` para llenar el tablero con la corrida representativa (la de confianza
  mediana). Todo va marcado SIMULADO; la vista `real` no cambia.
"""

from __future__ import annotations

import random
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Depends

from app.adapters.public_sources import load_snapshot
from app.auth import require_role
from app.core.recovery_dashboard import STAGES, stage_status
from app.core.scenarios import (
    SCENARIOS,
    SOURCES,
    ScenarioKey,
    Simulation,
    index_from,
    observe,
    simulate,
)
from app.domain import Role
from app.recovery_schemas import (
    BarrioRecovery,
    ConfidenceStat,
    CurvePoint,
    DashFigure,
    DashUnit,
    FigureState,
    Indicator,
    Need,
    RecoveryDashboard,
    ScenarioComparison,
    ScenarioSummary,
    SourceInfo,
    Stage,
)

router = APIRouter(prefix="/recovery", tags=["recuperación"])

RUNS = 2000
WEIGHTS = {"cobertura": 0.30, "frescura": 0.20, "exactitud": 0.35, "unicidad": 0.15}
METHOD = (
    "Monte Carlo de {runs} corridas por escenario sobre una misma verdad SIMULADA del sismo en el "
    "día {day}. Confianza = 30 % cobertura + 20 % frescura (cadencia EMRE) + 35 % exactitud "
    "(cifras dentro de ±10 %, o ±5 puntos en porcentajes) + 15 % duplicados detectados. "
    "IC del 90 % = percentiles 5 y 95."
)
FEEDS = {
    "dacora": "1, 2, 3, 4, 7",
    "alcaldia": "2 y etapa 1",
    "servicios": "6 y 4",
    "economia": "9, 4 y etapa 4",
    "finanzas": "10 y etapas 2 y 3",
    "estabilizacion": "etapa 5",
}
HARD_HIT = {"Centro", "Milán", "Los Agustinos", "Fundadores", "San José", "Galán", "Palermo"}


def event_day(now: datetime) -> tuple[int, datetime | None, str | None, str | None]:
    usgs = load_snapshot("usgs_sismos")
    if not usgs or not usgs.records:
        return 0, None, None, None
    main = max(usgs.records, key=lambda r: r["magnitude"])
    at = datetime.fromisoformat(main["time"])
    return max((now - at).days, 0), at, f"M {main['magnitude']} · {main['place']}", main["url"]


@lru_cache(maxsize=8)
def cached_simulation(key: ScenarioKey, day: int) -> Simulation:
    return simulate(key, day, runs=RUNS)


def _summary(sim: Simulation) -> ScenarioSummary:
    return ScenarioSummary(
        key=sim.params.key,
        title=sim.params.title,
        description=sim.params.description,
        assumptions=list(sim.params.assumptions),
        runs=sim.runs,
        seed=sim.seed,
        p_high_confidence=sim.p_high_confidence,
        stats=[ConfidenceStat(**vars(s)) for s in sim.stats],
    )


@router.get("/scenarios", response_model=ScenarioComparison)
async def scenarios(
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
) -> ScenarioComparison:
    """Confianza del sistema en el mejor y el peor caso de acceso a datos (SIMULADO)."""
    from datetime import UTC

    day, *_rest = event_day(datetime.now(UTC))
    return ScenarioComparison(
        day=day,
        method=METHOD.format(runs=RUNS, day=day),
        weights=WEIGHTS,
        scenarios=[_summary(cached_simulation(k, day)) for k in ("mejor", "peor")],
    )


# ------------------------------------------------------------------- tablero de un escenario


def _components(v: dict[str, float | None]) -> dict[str, float | None]:
    """Los cuatro componentes del índice, cada uno solo si su fuente entregó dato."""

    def one(keys: list[str]) -> float | None:
        return index_from({k: v.get(k) for k in keys})

    colors = [f"predios_{c}" for c in ("verde", "amarillo", "rojo", "colapso")]
    families = [f"familias_{k}" for k in ("albergue", "arriendo", "casa", "sin_solucion")]
    services = [f"servicio_{s}" for s in ("agua", "energia", "gas", "telecom", "vias")]
    comps = {
        "habitabilidad": one(colors),
        "familias": one(families),
        "servicios": one(services),
        "economia": one(["negocios_cerrados", "negocios_reabiertos"]),
    }
    return {k: round(c, 1) if c is not None else None for k, c in comps.items()}


def scenario_dashboard(key: ScenarioKey, now: datetime) -> RecoveryDashboard:  # noqa: C901
    day, event_at, event_label, event_url = event_day(now)
    sim = cached_simulation(key, day)
    obs, run = sim.representative, sim.representative_metrics
    v = obs.values
    label = "mejor caso" if key == "mejor" else "peor caso"

    def fig(
        k: str,
        title: str,
        source: str,
        unit: DashUnit = "conteo",
        value: float | None = None,
        state: FigureState = "neutral",
        target: str | None = None,
    ) -> DashFigure:
        val = v.get(k) if value is None else value
        if val is None:
            return DashFigure(
                key=k,
                label=title,
                value=None,
                unit=unit,
                source=SOURCES[source],
                version=0,
                cutoff_at=now,
                simulated=True,
                state="sin_fuente",
                note=f"En este corte del {label} la fuente no entregó dato ({SOURCES[source]}).",
            )
        return DashFigure(
            key=k,
            label=title,
            value=round(val, 1),
            unit=unit,
            source=f"{SOURCES[source]} · SIMULADO ({label})",
            version=1,
            cutoff_at=now,
            simulated=True,
            target=target,
            state=state,
        )

    def get(k: str) -> float | None:
        return v.get(k)

    evaluated, requested = get("predios_evaluados"), get("solicitudes")
    pending = max(requested - evaluated, 0) if requested and evaluated is not None else None
    loss, available = get("perdida"), get("recursos")
    gap = max(loss - available, 0) if loss and available is not None else None
    index = index_from(v)
    index_true = index_from(dict(obs.truth))
    svc_keys = ("agua", "energia", "gas", "telecom", "vias")

    indicators = [
        Indicator(
            number=1,
            key="familias_damnificadas",
            title="Familias damnificadas únicas",
            block="encabezado",
            source=SOURCES["dacora"],
            figures=[
                fig("familias_unicas", "Familias únicas (HMAC)", "dacora"),
                fig("personas", "Personas damnificadas", "dacora"),
            ],
        ),
        Indicator(
            number=2,
            key="predios_evaluados",
            title="Predios evaluados únicos contra pendientes",
            block="encabezado",
            source=f"{SOURCES['dacora']} · {SOURCES['alcaldia']}",
            figures=[
                fig("predios_evaluados", "Predios evaluados únicos", "dacora"),
                fig("solicitudes", "Predios con solicitud de visita", "alcaldia"),
                fig(
                    "pendientes",
                    "Predios pendientes de visita",
                    "alcaldia",
                    value=pending,
                    state="alerta" if pending else "neutral",
                ),
                fig(
                    "repetidos_sin_unir",
                    "Registros repetidos sin unir",
                    "dacora",
                    "%",
                    value=100 * obs.duplicates_left,
                    state="alerta" if obs.duplicates_left > 0.05 else "ok",
                ),
            ],
        ),
        Indicator(
            number=3,
            key="semaforo_nsr10",
            title="Viviendas por semáforo NSR-10",
            block="encabezado",
            source=SOURCES["dacora"],
            figures=[
                fig("predios_verde", "Verde · habitable", "dacora"),
                fig("predios_amarillo", "Amarillo · uso restringido", "dacora"),
                fig("predios_rojo", "Rojo · no habitable", "dacora"),
                fig("predios_colapso", "Colapsado", "dacora"),
            ],
        ),
        Indicator(
            number=4,
            key="indice_recuperacion",
            title="Índice de recuperación",
            block="encabezado",
            source="Calculado por Dacora (indicadores 3, 6, 7 y 9)",
            figures=[
                fig("indice_recuperacion", "Índice que ve el tablero", "dacora", "%", index),
                fig(
                    "indice_real",
                    "Índice real de la simulación",
                    "dacora",
                    "%",
                    index_true,
                ),
                fig(
                    "error_indice",
                    "Diferencia contra la realidad (puntos)",
                    "dacora",
                    "conteo",
                    abs(index - index_true) if index is not None and index_true else None,
                    state="ok"
                    if index is not None and index_true and abs(index - index_true) <= 3
                    else "alerta",
                ),
            ],
        ),
        Indicator(
            number=5,
            key="riesgo_activo",
            title="Días desde el evento y riesgo activo",
            block="encabezado",
            source="USGS (evento real)",
            figures=[
                DashFigure(
                    key="dias_desde_evento",
                    label="Días desde el sismo",
                    value=day,
                    unit="dias",
                    source="USGS · servicio FDSN",
                    version=1,
                    cutoff_at=event_at or now,
                    source_url=event_url,
                ),
            ],
        ),
        Indicator(
            number=6,
            key="servicios_basicos",
            title="Servicios básicos",
            block="operacion",
            source=SOURCES["servicios"],
            figures=[
                fig(f"servicio_{s}", name, "servicios", "%")
                for s, name in zip(
                    svc_keys, ("Agua", "Energía", "Gas", "Telecomunicaciones", "Vías"), strict=True
                )
            ],
        ),
        Indicator(
            number=7,
            key="familias_situacion",
            title="Familias por situación y ayudas",
            block="operacion",
            source=SOURCES["dacora"],
            figures=[
                fig("familias_albergue", "En albergue", "dacora"),
                fig("familias_arriendo", "En arriendo temporal", "dacora"),
                fig("familias_casa", "En casa", "dacora"),
                fig(
                    "familias_sin_solucion",
                    "Predio rojo sin solución de vivienda",
                    "dacora",
                    state="alerta" if (get("familias_sin_solucion") or 0) > 0 else "ok",
                ),
                fig("ayudas", "Ayudas entregadas", "dacora"),
            ],
        ),
        Indicator(
            number=8,
            key="calidad_datos",
            title="Calidad de los datos en este corte",
            block="operacion",
            source="Medido contra la verdad de la simulación",
            figures=[
                fig("cobertura", "Cifras con dato", "dacora", "%", run.cobertura),
                fig("frescura", "Dentro de la cadencia EMRE", "dacora", "%", run.frescura),
                fig(
                    "exactitud",
                    "Dentro de ±10 % de la realidad",
                    "dacora",
                    "%",
                    run.exactitud,
                    state="ok" if run.exactitud >= 75 else "alerta",
                    target="≥ 75 %",
                ),
                fig("unicidad", "Duplicados detectados", "dacora", "%", run.unicidad),
                fig(
                    "confianza",
                    "Confianza del corte",
                    "dacora",
                    "%",
                    run.confianza,
                    state="ok" if run.confianza >= 75 else "alerta",
                    target="≥ 75 %",
                ),
            ],
        ),
        Indicator(
            number=9,
            key="negocios_empleo",
            title="Negocios reabiertos y empleos recuperados",
            block="economia",
            source=SOURCES["economia"],
            figures=[
                fig("negocios_reabiertos", "Negocios reabiertos", "economia"),
                fig("negocios_cerrados", "Negocios cerrados por el sismo", "economia"),
                fig("empleos_recuperados", "Empleos recuperados", "economia"),
                fig("empleos_perdidos", "Empleos detenidos", "economia"),
            ],
        ),
        Indicator(
            number=10,
            key="recursos_trazabilidad",
            title="Recursos y trazabilidad",
            block="economia",
            source=SOURCES["finanzas"],
            figures=[
                fig("perdida", "Pérdida estimada", "finanzas", "cop"),
                fig("recursos", "Recursos disponibles", "finanzas", "cop"),
                fig(
                    "brecha",
                    "Brecha",
                    "finanzas",
                    "cop",
                    gap,
                    state="alerta" if gap else "neutral",
                ),
                fig("comprometido", "Comprometido", "finanzas", "cop"),
                fig("contratado", "Valor contratado", "finanzas", "cop"),
                fig("pagado", "Pagado", "finanzas", "cop"),
            ],
        ),
    ]

    # Curva: un corte observado cada 3 días con el mismo proceso de observación del escenario.
    curve: list[CurvePoint] = []
    rng = random.Random(f"curva-{key}-{day}")
    if event_at:
        from datetime import timedelta

        for d in range(0, day + 1, 3):
            value = index_from(observe(SCENARIOS[key], d, rng).values)
            if value is not None:
                curve.append(CurvePoint(at=event_at + timedelta(days=d), day=d, value=value))

    # Barrios: reparto proporcional SIMULADO del corte (más peso donde hubo más daño).
    from app.routers.recovery_dashboard import _barrio_comuna

    barrio_rng = random.Random(f"barrios-{key}-{day}")
    names = sorted(_barrio_comuna().items())
    weights = {n: (4.0 if n in HARD_HIT else 1.0) * barrio_rng.uniform(0.6, 1.4) for n, _ in names}
    total_w = sum(weights.values())
    svc_low = min((get(f"servicio_{s}") or 100.0) for s in svc_keys)
    barrios: list[BarrioRecovery] = []
    for name, comuna in names:
        share = weights[name] / total_w

        def part(k: str, share: float = share) -> int:
            val = get(k)
            return round(val * share) if val is not None else 0

        colors = {c: part(f"predios_{c}") for c in ("verde", "amarillo", "rojo", "colapso")}
        evaluated_b = sum(colors.values())
        fam = {k: part(f"familias_{k}") for k in ("albergue", "arriendo", "casa", "sin_solucion")}
        habit = (
            100 * (colors["verde"] + 0.5 * colors["amarillo"]) / evaluated_b
            if evaluated_b
            else None
        )
        home = 100 * fam["casa"] / sum(fam.values()) if sum(fam.values()) else None
        comps = [c for c in (habit, home) if c is not None]
        barrios.append(
            BarrioRecovery(
                barrio=name,
                comuna=comuna,
                index=round(sum(comps) / len(comps), 1) if comps else None,
                verde=colors["verde"],
                amarillo=colors["amarillo"],
                rojo=colors["rojo"],
                colapso=colors["colapso"],
                damage_reported=part("solicitudes"),
                pending=max(part("solicitudes") - evaluated_b, 0) if requested else 0,
                service_incidents=round((100 - svc_low) / 10 * share * 40),
                families=sum(fam.values()),
            )
        )

    # Etapas con su avance observado.
    def ratio(a: float | None, b: float | None) -> float | None:
        return a / b if a is not None and b else None

    stab = [get(k) for k in ("ica", "turismo", "cafe")]
    progress = [
        (ratio(evaluated, requested), "predios evaluados ÷ solicitudes de visita"),
        (ratio(available, loss), "recursos disponibles ÷ pérdida estimada"),
        (ratio(get("pagado"), get("contratado")), "pagado ÷ contratado"),
        (
            ratio(get("negocios_reabiertos"), get("negocios_cerrados")),
            "negocios reabiertos ÷ cerrados",
        ),
        (
            sum(x for x in stab if x is not None) / 300
            if all(x is not None for x in stab)
            else None,
            "promedio de ICA, turismo y café frente a antes",
        ),
    ]
    stage_figs = [
        [
            fig("predios_evaluados", "Predios evaluados", "dacora"),
            fig("perdida", "Pérdida estimada", "finanzas", "cop"),
        ],
        [
            fig("recursos", "Recursos disponibles", "finanzas", "cop"),
            fig("brecha", "Brecha", "finanzas", "cop", gap),
        ],
        [
            fig("contratado", "Contratado", "finanzas", "cop"),
            fig("pagado", "Pagado", "finanzas", "cop"),
            fig("ayudas", "Ayudas entregadas", "dacora"),
        ],
        [
            fig("negocios_reabiertos", "Negocios reabiertos", "economia"),
            fig("empleos_recuperados", "Empleos recuperados", "economia"),
        ],
        [
            fig("ica", "Recaudo ICA vs. antes", "estabilizacion", "%"),
            fig("turismo", "Turismo vs. antes", "estabilizacion", "%"),
            fig("cafe", "Café vs. antes", "estabilizacion", "%"),
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
            progress_basis=basis,
            figures=f,
        )
        for w, (p, basis), f in zip(STAGES, progress, stage_figs, strict=True)
    ]

    # Necesidades del escenario.
    needs: list[Need] = []
    down = [SOURCES[s] for s, up in obs.source_up.items() if not up]
    if down:
        needs.append(
            Need(
                key="fuentes_caidas",
                title="Fuentes que no entregaron dato en este corte",
                detail="; ".join(down),
                severity="critica" if len(down) >= 3 else "alta",
                value=len(down),
            )
        )
    if run.exactitud < 75:
        needs.append(
            Need(
                key="exactitud_baja",
                title="Cifras del tablero lejos de la realidad",
                detail=(
                    f"Solo {run.exactitud:.0f} % de las cifras queda dentro de ±10 % de la verdad: "
                    "las decisiones necesitan verificación en terreno."
                ),
                severity="critica",
                value=round(100 - run.exactitud),
            )
        )
    if (get("familias_sin_solucion") or 0) > 0:
        needs.append(
            Need(
                key="familias_sin_solucion",
                title="Familias en predio rojo sin solución de vivienda",
                detail="Asignar albergue o subsidio de arriendo.",
                severity="critica",
                value=round(get("familias_sin_solucion") or 0),
            )
        )
    if pending:
        needs.append(
            Need(
                key="predios_pendientes",
                title="Predios con solicitud de visita sin evaluar",
                detail="Priorizar las manzanas con más daño reportado.",
                severity="alta",
                value=round(pending),
            )
        )
    lagging = [s for s in svc_keys if (get(f"servicio_{s}") or 100) < 95]
    if lagging:
        needs.append(
            Need(
                key="servicios_rezagados",
                title="Servicios básicos por debajo de 95 % de cobertura",
                detail=", ".join(lagging),
                severity="media",
                value=len(lagging),
            )
        )
    if gap:
        needs.append(
            Need(
                key="brecha_financiera",
                title="Brecha entre pérdida estimada y recursos disponibles",
                detail=f"Faltan {round(gap / 1e9):,} mil millones de pesos.".replace(",", "."),
                severity="media",
                value=round(gap / 1e9),
            )
        )

    sources = [
        SourceInfo(
            key=s,
            title=f"{name} (SIMULADO)",
            source=f"Escenario {label}",
            status="conectada" if obs.source_up[s] else "sin_copia",
            fetched_at=now,
            attribution=(
                f"Disponibilidad supuesta: {SCENARIOS[key].availability[s]:.0%} de los cortes"
            ),
            feeds=FEEDS[s],
        )
        for s, name in SOURCES.items()
    ]

    return RecoveryDashboard(
        scenario=key,
        scenario_title=sim.params.title,
        scenario_note=(
            f"SIMULADO. Corrida representativa (confianza mediana {run.confianza:.0f} %) de "
            f"{sim.runs} corridas. {sim.params.description}"
        ),
        cutoff_at=now,
        event_at=event_at,
        event_label=event_label,
        event_url=event_url,
        day=day,
        index=round(index, 1) if index is not None else None,
        index_components=_components(v),
        needs=needs,
        indicators=indicators,
        barrios=barrios,
        index_curve=curve,
        channels=[],
        contracts=[],
        sources=sources,
        stages=stages,
    )
