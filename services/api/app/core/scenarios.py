"""Escenarios SIMULADOS del tablero de recuperación: mejor y peor caso de acceso a datos.

Pregunta: ¿cuánta confianza tendría Dacora según cómo le lleguen los datos? Se simula **una sola
verdad** del sismo (predios, familias, servicios, economía y finanzas evolucionando con los días)
y dos **procesos de observación**:

- `mejor`: instituciones que colaboran con convenios, fuentes constantes, identificador único de
  predio y hogar, reportes a tiempo con la cadencia EMRE.
- `peor`: fuentes intermitentes o ausentes (cortes de energía y red), subregistro alto, cifras que
  cambian entre cortes (como 1.449 → 2.700 → 1.512 viviendas), duplicados sin identificador común
  y retrasos de días.

Como la verdad es conocida, el error del tablero se **mide** (no se supone) con Monte Carlo:
cobertura, frescura, exactitud, unicidad, error del índice y una confianza global 0–100, con media
e intervalo de confianza del 90 %. Todo es SIMULADO y determinista (semilla fija).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Literal

ScenarioKey = Literal["mejor", "peor"]
Kind = Literal["count", "pct", "cop"]

#: Fuentes del tablero (las mismas de la vista real, más las que hoy no tienen convenio).
SOURCES: dict[str, str] = {
    "dacora": "Registro de Dacora (censo, inspecciones, ayudas)",
    "alcaldia": "Alcaldía / UGR (solicitudes de visita)",
    "servicios": "Aguas de Manizales, CHEC, Efigas y Obras Públicas",
    "economia": "Cámara de Comercio y DANE",
    "finanzas": "Hacienda, UNGRD, SECOP II y aseguradoras",
    "estabilizacion": "Hacienda (ICA), Cotelco y Comité de Cafeteros",
}


#: Cadencia EMRE de reportes de situación (horas) según el día desde el evento.
def emre_cadence_h(day: int) -> float:
    return 6.0 if day < 3 else 12.0 if day < 5 else 24.0


@dataclass(frozen=True)
class Params:
    """Proceso de observación de un escenario."""

    key: ScenarioKey
    title: str
    description: str
    availability: dict[str, float]  # probabilidad de que la fuente entregue dato en el corte
    coverage_mean: float  # fracción de la realidad que llega a registrarse (subregistro)
    coverage_sd: float
    noise_sd: float  # error relativo de medición en conteos y montos
    pct_noise_pts: float  # error absoluto en porcentajes (puntos)
    duplicate_rate: float  # reportes/registros repetidos del mismo hecho
    duplicate_detection: float  # fracción de duplicados que el sistema logra unir
    latency_mean_h: float  # edad media del dato al momento del corte
    assumptions: tuple[str, ...]


SCENARIOS: dict[ScenarioKey, Params] = {
    "mejor": Params(
        key="mejor",
        title="Mejor caso: colaboración institucional y datos constantes",
        description=(
            "Convenios activos con todas las entidades, identificador único de predio y hogar, "
            "red disponible y reportes con la cadencia de la EMRE."
        ),
        availability={
            "dacora": 0.99,
            "alcaldia": 0.97,
            "servicios": 0.95,
            "economia": 0.92,
            "finanzas": 0.95,
            "estabilizacion": 0.90,
        },
        coverage_mean=0.97,
        coverage_sd=0.02,
        noise_sd=0.03,
        pct_noise_pts=2.0,
        duplicate_rate=0.12,
        duplicate_detection=0.97,
        latency_mean_h=4.0,
        assumptions=(
            "Cada fuente entrega dato en 90–99 % de los cortes.",
            "Se registra ~97 % de la realidad (subregistro ~3 %).",
            "Error de medición ~3 % en conteos y montos; ±2 puntos en porcentajes.",
            "12 % de registros repetidos; 97 % se unen por identificador único.",
            "Edad media del dato: 4 h (cadencia EMRE: 6–24 h).",
        ),
    ),
    "peor": Params(
        key="peor",
        title="Peor caso: datos inconsistentes o ausentes",
        description=(
            "Sin convenios, cortes de energía y red celular, cifras que cambian entre cortes, "
            "sin identificador común entre entidades y reportes atrasados días."
        ),
        availability={
            "dacora": 0.70,
            "alcaldia": 0.45,
            "servicios": 0.10,
            "economia": 0.05,
            "finanzas": 0.20,
            "estabilizacion": 0.05,
        },
        coverage_mean=0.55,
        coverage_sd=0.20,
        noise_sd=0.25,
        pct_noise_pts=15.0,
        duplicate_rate=0.35,
        duplicate_detection=0.55,
        latency_mean_h=60.0,
        assumptions=(
            "Solo el registro propio entrega dato con regularidad (70 %); servicios, economía y "
            "estabilización casi nunca (5–10 %).",
            "Se registra ~55 % de la realidad, con mucha variación entre cortes (±20 %).",
            "Error de medición ~25 %; ±15 puntos en porcentajes.",
            "35 % de registros repetidos; solo 55 % se unen (sin identificador común).",
            "Edad media del dato: 60 h, muy por encima de la cadencia EMRE.",
        ),
    ),
}


@dataclass(frozen=True)
class Truth:
    """Verdad SIMULADA del sismo en un día dado (ciudad)."""

    key: str
    label: str
    source: str
    kind: Kind
    value: float


def recovery_curve(day: int) -> float:
    """Avance de la recuperación 0–1 (logística: lenta al inicio, se estabiliza hacia el día 90)."""
    return 1.0 / (1.0 + math.exp(-(day - 35) / 11))


SERVICE_DROP = {  # caída inicial (puntos) y tiempo de recuperación (días)
    "agua": (35.0, 12.0),
    "energia": (40.0, 6.0),
    "gas": (60.0, 20.0),
    "telecom": (30.0, 5.0),
    "vias": (25.0, 25.0),
}


def truth(day: int) -> list[Truth]:
    """Verdad de la ciudad en el día `day`. Escala inspirada en el evento real (~2.000 predios)."""
    r = recovery_curve(day)
    damaged = 2000.0
    evaluated = damaged * min(1.0, 0.15 + 0.85 * r)
    shares = {
        "verde": 0.45 + 0.15 * r,
        "amarillo": 0.30 - 0.08 * r,
        "rojo": 0.20 - 0.06 * r,
        "colapso": 0.05 - 0.01 * r,
    }
    total_share = sum(shares.values())
    families = 2700.0
    sit = {
        "albergue": 0.30 * (1 - r) + 0.03,
        "arriendo": 0.25 + 0.10 * r,
        "casa": 0.25 + 0.45 * r,
    }
    sit["sin_solucion"] = max(0.02, 1 - sum(sit.values()))
    norm = sum(sit.values())
    closed, jobs = 1600.0, 7700.0
    loss = 1.84e12
    available = loss * (0.35 + 0.40 * min(1.0, day / 15))
    committed = available * 0.85 * min(1.0, day / 30)
    contracted = committed * 0.70 * min(1.0, 0.2 + r)
    paid = contracted * 0.60 * r
    rows = [
        Truth("familias_unicas", "Familias damnificadas únicas", "dacora", "count", families),
        Truth("personas", "Personas damnificadas", "dacora", "count", families * 3.1),
        Truth("predios_evaluados", "Predios evaluados únicos", "dacora", "count", evaluated),
        Truth("solicitudes", "Predios con solicitud de visita", "alcaldia", "count", damaged),
        *[
            Truth(
                f"predios_{c}",
                f"Predios {c}",
                "dacora",
                "count",
                evaluated * s / total_share,
            )
            for c, s in shares.items()
        ],
        *[
            Truth(f"familias_{k}", f"Familias: {k}", "dacora", "count", families * v / norm)
            for k, v in sit.items()
        ],
        Truth("ayudas", "Ayudas entregadas", "dacora", "count", families * (1.2 + 2.5 * r)),
        *[
            Truth(
                f"servicio_{s}",
                f"Cobertura {s}",
                "servicios",
                "pct",
                100 - drop * math.exp(-day / tau),
            )
            for s, (drop, tau) in SERVICE_DROP.items()
        ],
        Truth("negocios_cerrados", "Negocios cerrados", "economia", "count", closed),
        Truth("negocios_reabiertos", "Negocios reabiertos", "economia", "count", closed * 0.8 * r),
        Truth("empleos_perdidos", "Empleos detenidos", "economia", "count", jobs),
        Truth("empleos_recuperados", "Empleos recuperados", "economia", "count", jobs * 0.75 * r),
        Truth("perdida", "Pérdida estimada", "finanzas", "cop", loss),
        Truth("recursos", "Recursos disponibles", "finanzas", "cop", available),
        Truth("comprometido", "Comprometido", "finanzas", "cop", committed),
        Truth("contratado", "Contratado", "finanzas", "cop", contracted),
        Truth("pagado", "Pagado", "finanzas", "cop", paid),
        Truth("ica", "Recaudo ICA vs. antes", "estabilizacion", "pct", 70 + 25 * r),
        Truth("turismo", "Turismo vs. antes", "estabilizacion", "pct", 55 + 35 * r),
        Truth("cafe", "Café vs. antes", "estabilizacion", "pct", 80 + 18 * r),
    ]
    return rows


def index_from(values: dict[str, float | None]) -> float | None:
    """Índice de recuperación con los mismos 4 componentes del tablero real."""

    def g(k: str) -> float | None:
        return values.get(k)

    comps: list[float] = []
    ev = [g(f"predios_{c}") for c in ("verde", "amarillo", "rojo", "colapso")]
    if all(v is not None for v in ev) and sum(v for v in ev if v is not None) > 0:
        verde, amarillo, rojo, colapso = (v or 0.0 for v in ev)
        comps.append(100 * (verde + 0.5 * amarillo) / (verde + amarillo + rojo + colapso))
    svc = [g(f"servicio_{s}") for s in SERVICE_DROP]
    if all(v is not None for v in svc):
        comps.append(sum(v for v in svc if v is not None) / len(svc))
    fam = [g(f"familias_{k}") for k in ("albergue", "arriendo", "casa", "sin_solucion")]
    if all(v is not None for v in fam) and sum(v for v in fam if v is not None) > 0:
        comps.append(100 * (g("familias_casa") or 0.0) / sum(v for v in fam if v is not None))
    closed, reopened = g("negocios_cerrados"), g("negocios_reabiertos")
    if closed and reopened is not None:
        comps.append(100 * reopened / closed)
    return sum(comps) / len(comps) if comps else None


@dataclass
class Observation:
    """Lo que el tablero vería en un corte de un escenario."""

    values: dict[str, float | None]
    fresh: dict[str, bool]
    source_up: dict[str, bool]
    detection: float
    duplicates_left: float  # fracción de registros duplicados que quedan sin unir
    truth: dict[str, float] = field(default_factory=dict)


def observe(p: Params, day: int, rng: random.Random) -> Observation:
    rows = truth(day)
    cadence = emre_cadence_h(day)
    up = {s: rng.random() < p.availability[s] for s in SOURCES}
    age = {s: rng.expovariate(1 / p.latency_mean_h) for s in SOURCES}
    coverage = min(1.05, max(0.05, rng.gauss(p.coverage_mean, p.coverage_sd)))
    detection = min(1.0, max(0.0, rng.gauss(p.duplicate_detection, 0.03)))
    dup_left = p.duplicate_rate * (1 - detection)
    values: dict[str, float | None] = {}
    fresh: dict[str, bool] = {}
    for t in rows:
        if not up[t.source]:
            values[t.key] = None
            fresh[t.key] = False
            continue
        if t.kind == "pct":
            v = t.value + rng.gauss(0, p.pct_noise_pts)
            values[t.key] = min(100.0, max(0.0, v))
        else:
            factor = coverage * max(0.0, rng.gauss(1, p.noise_sd))
            if t.source == "dacora" and t.kind == "count":
                factor *= 1 + dup_left  # los repetidos sin unir inflan los conteos
            values[t.key] = max(0.0, t.value * factor)
        fresh[t.key] = age[t.source] <= cadence
    return Observation(
        values=values,
        fresh=fresh,
        source_up=up,
        detection=detection,
        duplicates_left=dup_left,
        truth={t.key: t.value for t in rows},
    )


def accurate(kind: Kind, observed: float, real: float) -> bool:
    """Dentro de ±10 % en conteos y montos; ±5 puntos en porcentajes."""
    if kind == "pct":
        return abs(observed - real) <= 5.0
    return real > 0 and abs(observed - real) / real <= 0.10


@dataclass(frozen=True)
class RunMetrics:
    cobertura: float  # % de cifras con dato
    frescura: float  # % de cifras con dato dentro de la cadencia EMRE
    exactitud: float  # % de cifras (sobre el total) dentro de la tolerancia
    unicidad: float  # % de duplicados detectados
    error_indice: float | None  # puntos de diferencia entre el índice observado y el real
    mape: float | None  # error relativo medio de las cifras con dato (%)
    confianza: float  # 0-100


def metrics(p: Params, day: int, obs: Observation) -> RunMetrics:
    rows = truth(day)
    total = len(rows)
    have = [t for t in rows if obs.values[t.key] is not None]
    ok = [t for t in have if accurate(t.kind, obs.values[t.key] or 0.0, t.value)]
    errors = [
        abs((obs.values[t.key] or 0.0) - t.value) / t.value * 100
        for t in have
        if t.kind != "pct" and t.value > 0
    ] + [abs((obs.values[t.key] or 0.0) - t.value) for t in have if t.kind == "pct"]
    idx_obs = index_from(obs.values)
    idx_true = index_from(dict(obs.truth))
    cobertura = 100 * len(have) / total
    frescura = 100 * sum(1 for t in have if obs.fresh[t.key]) / total
    exactitud = 100 * len(ok) / total
    unicidad = 100 * obs.detection
    confianza = 0.30 * cobertura + 0.20 * frescura + 0.35 * exactitud + 0.15 * unicidad
    return RunMetrics(
        cobertura=cobertura,
        frescura=frescura,
        exactitud=exactitud,
        unicidad=unicidad,
        error_indice=abs(idx_obs - idx_true) if idx_obs is not None and idx_true else None,
        mape=statistics.fmean(errors) if errors else None,
        confianza=confianza,
    )


@dataclass(frozen=True)
class Stat:
    key: str
    label: str
    unit: Literal["%", "pts"]
    mean: float
    p5: float
    p50: float
    p95: float
    n: int


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _stat(key: str, label: str, unit: Literal["%", "pts"], xs: list[float]) -> Stat:
    return Stat(
        key=key,
        label=label,
        unit=unit,
        mean=round(statistics.fmean(xs), 1),
        p5=round(_quantile(xs, 0.05), 1),
        p50=round(_quantile(xs, 0.50), 1),
        p95=round(_quantile(xs, 0.95), 1),
        n=len(xs),
    )


@dataclass(frozen=True)
class Simulation:
    params: Params
    day: int
    runs: int
    seed: int
    stats: tuple[Stat, ...]
    p_high_confidence: float  # % de corridas con confianza ≥ 75
    representative: Observation  # corrida con la confianza más cercana a la mediana
    representative_metrics: RunMetrics


def simulate(key: ScenarioKey, day: int, runs: int = 2000, seed: int = 20260810) -> Simulation:
    p = SCENARIOS[key]
    rng = random.Random(f"{seed}-{key}-{day}")
    observed: list[tuple[Observation, RunMetrics]] = []
    for _ in range(runs):
        obs = observe(p, day, rng)
        observed.append((obs, metrics(p, day, obs)))
    ms = [m for _, m in observed]
    conf = [m.confianza for m in ms]
    median = _quantile(conf, 0.5)
    rep_obs, rep_m = min(observed, key=lambda om: abs(om[1].confianza - median))
    idx = [m.error_indice for m in ms if m.error_indice is not None]
    mape = [m.mape for m in ms if m.mape is not None]
    stats = [
        _stat("confianza", "Confianza global del sistema", "%", conf),
        _stat("cobertura", "Cobertura: cifras con dato", "%", [m.cobertura for m in ms]),
        _stat(
            "frescura", "Frescura: dato dentro de la cadencia EMRE", "%", [m.frescura for m in ms]
        ),
        _stat(
            "exactitud",
            "Exactitud: cifras dentro de ±10 % de la realidad",
            "%",
            [m.exactitud for m in ms],
        ),
        _stat("unicidad", "Duplicados detectados", "%", [m.unicidad for m in ms]),
    ]
    if mape:
        stats.append(_stat("mape", "Error medio de las cifras con dato", "%", mape))
    if idx:
        stats.append(_stat("error_indice", "Error del índice de recuperación", "pts", idx))
    return Simulation(
        params=p,
        day=day,
        runs=runs,
        seed=seed,
        stats=tuple(stats),
        p_high_confidence=round(100 * sum(1 for c in conf if c >= 75) / runs, 1),
        representative=rep_obs,
        representative_metrics=rep_m,
    )
