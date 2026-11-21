"""Clasificación por reglas en español colombiano (research R6, FR-010, FR-011).

Determinista y explicable: cada decisión se puede rastrear a las expresiones que la dispararon.
Matriz de triaje: CLAUDE.md §7.2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.text import normalize
from app.domain import TRIAGE_RANK, Category, TriageLevel

# Expresiones normalizadas (sin tildes). Coinciden al inicio de palabra (prefijos).
LEXICON: dict[Category, tuple[str, ...]] = {
    Category.personas_atrapadas: (
        "atrapad",
        "bajo los escombros",
        "entre los escombros",
        "bajo escombros",
        "no pueden salir",
        "no puede salir",
        "quedaron adentro",
        "quedo adentro",
        "gente adentro",
        "personas adentro",
        "sepultad",
        "encerrad",
        "se escuchan gritos",
        "piden auxilio",
    ),
    Category.heridos: (
        "herid",
        "lesionad",
        "sangr",
        "fractur",
        "inconsciente",
        "ambulancia",
        "paramedic",
        "desmayad",
        "aplastad",
        "necesitamos medico",
    ),
    Category.colapso_estructura: (
        "colaps",
        "se derrumb",
        "derrumbe de",
        "edificio caido",
        "casa caida",
        "se vino abajo",
        "desplom",
        "se cayo el edificio",
        "se cayo la casa",
        "se cayo un edificio",
        "se cayo una casa",
        "se cayo la iglesia",
        "se cayo la catedral",
    ),
    Category.dano_estructural: (
        "griet",
        "fisura",
        "agriet",
        "pared",
        "techo",
        "muro",
        "columna",
        "tejas",
        "fachada",
        "cornisa",
        "inclinad",
        "dano en",
        "danos en",
        "danad",
    ),
    Category.incendio: ("incendi", "fuego", "llamas", "se quema", "quemando", "humo", "conato"),
    Category.fuga_gas: ("gas", "fuga", "olor a gas", "escape de"),
    Category.deslizamiento: (
        "desliz",
        "derrumbe de tierra",
        "alud",
        "talud",
        "avalancha",
        "barranco",
        "movimiento en masa",
        "lodo",
        "se vino la montana",
        "se vino la ladera",
    ),
    Category.via_bloqueada: (
        "via bloqueada",
        "via cerrada",
        "bloquead",
        "no hay paso",
        "obstruid",
        "cerrada la via",
        "puente",
        "trancon",
    ),
    Category.servicios_caidos: (
        "sin luz",
        "sin energia",
        "sin agua",
        "sin gas",
        "se fue la luz",
        "no hay luz",
        "no hay agua",
        "sin senal",
        "sin internet",
        "apagon",
        "transformador",
        "poste caido",
        "cables caidos",
        "cortes de",
    ),
    Category.necesidad_albergue: (
        "albergue",
        "donde dormir",
        "sin casa",
        "sin techo",
        "refugio",
        "quedamos en la calle",
        "carpa",
        "damnificad",
    ),
    Category.necesidad_ayuda: (
        "necesitamos agua",
        "comida",
        "mercado",
        "alimento",
        "medicamento",
        "medicina",
        "panales",
        "frazada",
        "cobija",
        "ayuda humanitaria",
        "donacion",
    ),
    Category.persona_desaparecida: (
        "desaparecid",
        "no aparece",
        "no sabemos nada de",
        "no contesta",
        "extraviad",
        "busco a",
        "buscamos a",
    ),
    Category.sismo_sentido: (
        "se sintio",
        "temblor",
        "temblo",
        "sismo fuerte",
        "se movio todo",
        "que susto",
        "fuerte movimiento",
        "terremoto",
        "sentimos",
    ),
}

# Señales de desinformación (CLAUDE.md §7.4). Nombre canónico → patrón normalizado.
MISINFO_PATTERNS: dict[str, str] = {
    "reenvia": r"reenvi\w*",
    "cadena": r"cadena",
    "dicen que": r"dicen que",
    "me contaron": r"me (?:contaron|dijeron que)",
    "urgente compartir": r"urgente compart\w*|compartan|difund\w*",
    "va a temblar": r"va a (?:temblar|haber otro)|viene (?:otro|un) terremoto",
    "prediccion de sismo": r"predic\w*|pronostic\w*|nasa",
    "cifra exagerada": r"(?:miles|cientos) de (?:muertos|heridos|desaparecidos)",
}
_REPLICA_RE = re.compile(r"(?<![a-z0-9])replica de (\d+)")

_PEOPLE_WORDS = re.compile(
    r"(?<![a-z0-9])(?:gente|personas|familia|familias|ninos|nino|adultos mayores|adentro|"
    r"habitantes|residentes|vecinos)"
)
_ON_HOMES = re.compile(r"(?<![a-z0-9])(?:vivienda|viviendas|casa|casas|familia|familias|tapo)")
_SEVERE = re.compile(
    r"(?<![a-z0-9])(?:column\w*|grave\w*|sever\w*|inclinad\w*|a punto de caer|se va a caer|"
    r"grandes?|colapsar|estructural)"
)
_MILD = re.compile(r"(?<![a-z0-9])(?:leve\w*|pequen\w*|superficial\w*|menor\w*)")
_CRITICAL_ROUTE = re.compile(r"(?<![a-z0-9])(?:hospital|clinica|albergue|ambulancia\w*)")

BASE_TRIAGE: dict[Category, TriageLevel] = {
    Category.personas_atrapadas: TriageLevel.critico,
    Category.heridos: TriageLevel.critico,
    Category.colapso_estructura: TriageLevel.alto,
    Category.dano_estructural: TriageLevel.medio,
    Category.incendio: TriageLevel.critico,
    Category.fuga_gas: TriageLevel.critico,
    Category.deslizamiento: TriageLevel.alto,
    Category.via_bloqueada: TriageLevel.medio,
    Category.servicios_caidos: TriageLevel.medio,
    Category.necesidad_albergue: TriageLevel.medio,
    Category.necesidad_ayuda: TriageLevel.medio,
    Category.persona_desaparecida: TriageLevel.alto,
    Category.sismo_sentido: TriageLevel.bajo,
    Category.rumor_informacion: TriageLevel.bajo,
    Category.sin_clasificar: TriageLevel.medio,
}

SEVERITY: dict[TriageLevel, int] = {
    TriageLevel.critico: 5,
    TriageLevel.alto: 4,
    TriageLevel.medio: 3,
    TriageLevel.bajo: 2,
}

_COMPILED: dict[Category, list[re.Pattern[str]]] = {
    cat: [re.compile(rf"(?<![a-z0-9]){re.escape(p)}") for p in phrases]
    for cat, phrases in LEXICON.items()
}
_MISINFO_COMPILED = {
    name: re.compile(rf"(?<![a-z0-9])(?:{pat})") for name, pat in MISINFO_PATTERNS.items()
}


@dataclass(frozen=True)
class Classification:
    category: Category
    triage_level: TriageLevel
    is_life_threat: bool
    severity: int
    misinfo_signals: list[str] = field(default_factory=list)
    matched: dict[str, list[str]] = field(default_factory=dict)


def misinformation_signals(norm: str) -> list[str]:
    signals = [name for name, pat in _MISINFO_COMPILED.items() if pat.search(norm)]
    for match in _REPLICA_RE.finditer(norm):
        if int(match.group(1)) >= 7:
            signals.append(f"replica de {match.group(1)}")
    return signals


def _lexicon_scores(norm: str) -> dict[Category, list[str]]:
    hits: dict[Category, list[str]] = {}
    for cat, patterns in _COMPILED.items():
        found = [LEXICON[cat][i] for i, p in enumerate(patterns) if p.search(norm)]
        if found:
            hits[cat] = found
    return hits


def _pick(hits: dict[Category, list[str]]) -> Category:
    """Mayor nivel de triaje base; desempate por número de coincidencias y orden del léxico."""
    order = list(LEXICON)
    return max(
        hits,
        key=lambda c: (TRIAGE_RANK[BASE_TRIAGE[c]], len(hits[c]), -order.index(c)),
    )


def _triage(category: Category, norm: str, people: int | None) -> TriageLevel:
    has_people = bool(people) or bool(_PEOPLE_WORDS.search(norm))
    if category == Category.colapso_estructura and has_people:
        return TriageLevel.critico
    if category == Category.deslizamiento and (has_people or _ON_HOMES.search(norm)):
        return TriageLevel.critico
    if category == Category.dano_estructural:
        if _MILD.search(norm):
            return TriageLevel.bajo
        if _SEVERE.search(norm) or _CRITICAL_ROUTE.search(norm):
            return TriageLevel.alto
    if category == Category.via_bloqueada and _CRITICAL_ROUTE.search(norm):
        return TriageLevel.alto
    return BASE_TRIAGE[category]


def classify(
    text: str, *, hint: Category | None = None, people: int | None = None
) -> Classification:
    """Categoría, triaje, riesgo vital, gravedad y señales de desinformación de un reporte."""
    norm = normalize(text)
    signals = misinformation_signals(norm)
    hits = _lexicon_scores(norm)

    category: Category
    if hint is not None and hint not in (Category.sin_clasificar, Category.rumor_informacion):
        category = hint
    elif hits:
        category = _pick(hits)
    else:
        category = Category.rumor_informacion if signals else Category.sin_clasificar

    triage = _triage(category, norm, people)
    is_life_threat = triage == TriageLevel.critico

    # Lenguaje de cadena sin riesgo vital → rumor. Con riesgo vital se conserva (FR-013):
    # el puntaje baja, pero lo revisa un humano.
    if signals and not is_life_threat and category != Category.rumor_informacion:
        category = Category.rumor_informacion
        triage = TriageLevel.bajo

    severity = SEVERITY[triage]
    if category in (Category.sismo_sentido, Category.rumor_informacion):
        severity = 1

    return Classification(
        category=category,
        triage_level=triage,
        is_life_threat=is_life_threat,
        severity=severity,
        misinfo_signals=signals,
        matched={c.value: m for c, m in hits.items()},
    )
