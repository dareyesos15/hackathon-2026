"""A quién le llega cada incidente y plan de despacho multiagencia (EMRE Manizales 2024).

Reglas puras y deterministas: dada la categoría, el nivel de triaje, la confianza y el texto
redactado de los reportes, devuelven los actores que deben recibir la información y con qué
papel, citando la tarea EMRE que la justifica (anexos I–VI):

- `lider`: agencia responsable de la atención; se le propone recurso.
- `apoyo`: agencia que acompaña en sitio; se le propone recurso.
- `informada`: recibe el aviso para preparar su respuesta, sin recurso propuesto.

El COE/UGR (función 5, manejo y coordinación) se informa de todo lo crítico y de los rumores
(tarea 5.2, información pública). Nada aquí despacha: el plan es una propuesta que un humano
del PMU confirma (CLAUDE.md §0.6). Los reportes con riesgo vital siempre se avisan, aunque la
confianza sea baja; lo demás con "posible falso" queda retenido hasta la verificación humana.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.domain import Category, EmreFunction, RecipientRole, TriageLevel, TrustLabel

ROLE_RANK = {RecipientRole.lider: 0, RecipientRole.apoyo: 1, RecipientRole.informada: 2}

AGENCY_FUNCTION: dict[str, EmreFunction] = {
    "BOMBEROS": EmreFunction.salvamento_seguridad,
    "DEFENSA_CIVIL": EmreFunction.salvamento_seguridad,
    "POLICIA": EmreFunction.salvamento_seguridad,
    "CRUZ_ROJA": EmreFunction.salud_saneamiento,
    "SEC_SALUD": EmreFunction.salud_saneamiento,
    "SEC_DESARROLLO_SOCIAL": EmreFunction.asistencia_social,
    "SEC_INFRAESTRUCTURA": EmreFunction.infraestructura_servicios,
    "AGUAS_MANIZALES": EmreFunction.infraestructura_servicios,
    "CHEC": EmreFunction.infraestructura_servicios,
    "EFIGAS": EmreFunction.infraestructura_servicios,
}


@dataclass(frozen=True)
class Rule:
    agency: str
    role: RecipientRole
    task: str  # tarea EMRE, p. ej. "1.2 Búsqueda y rescate"
    reason: str


@dataclass(frozen=True)
class Recipient:
    agency: str
    role: RecipientRole
    emre_function: EmreFunction
    task: str
    reason: str

    @property
    def needs_resource(self) -> bool:
        return self.role != RecipientRole.informada


@dataclass(frozen=True)
class Routing:
    recipients: tuple[Recipient, ...]
    notify_coe: bool
    coe_reason: str | None
    held: bool
    hold_reason: str | None
    lead_units: int = 1
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def lead(self) -> Recipient | None:
        return next((r for r in self.recipients if r.role == RecipientRole.lider), None)

    def for_agency(self, code: str) -> Recipient | None:
        return next((r for r in self.recipients if r.agency == code), None)


L, A, INF = RecipientRole.lider, RecipientRole.apoyo, RecipientRole.informada

# Reglas base por categoría (CLAUDE.md §7.7 y anexos EMRE, §15).
BASE_RULES: dict[Category, tuple[Rule, ...]] = {
    Category.personas_atrapadas: (
        Rule("BOMBEROS", L, "1.2 Búsqueda y rescate", "Personas atrapadas"),
        Rule("CRUZ_ROJA", A, "2.1 Atención prehospitalaria", "Posibles lesionados al rescatar"),
        Rule("DEFENSA_CIVIL", A, "1.2 Búsqueda y rescate", "Apoyo en rescate"),
        Rule("POLICIA", A, "1.1 Aislamiento y seguridad", "Acordonar la zona"),
    ),
    Category.colapso_estructura: (
        Rule("BOMBEROS", L, "1.2 Búsqueda y rescate", "Estructura colapsada"),
        Rule("POLICIA", A, "1.1 Aislamiento y seguridad", "Acordonar la zona"),
        Rule(
            "SEC_INFRAESTRUCTURA",
            A,
            "4.2 Evaluación de daños en edificaciones",
            "Evaluar riesgo de nuevo colapso",
        ),
        Rule("CRUZ_ROJA", INF, "2.1 Atención prehospitalaria", "Posibles lesionados"),
        Rule("EFIGAS", INF, "4.4 Líneas vitales", "Revisar redes de gas en la estructura"),
    ),
    Category.incendio: (
        Rule("BOMBEROS", L, "1.3 Extinción de incendios", "Incendio activo"),
        Rule("POLICIA", A, "1.1 Aislamiento y seguridad", "Acordonar y evacuar"),
        Rule("CRUZ_ROJA", A, "2.1 Atención prehospitalaria", "Quemados o intoxicados"),
        Rule("EFIGAS", INF, "4.4 Líneas vitales", "Cortar el gas del sector"),
        Rule("CHEC", INF, "4.4 Líneas vitales", "Cortar la energía del sector"),
    ),
    Category.fuga_gas: (
        Rule("BOMBEROS", L, "1.4 Riesgos tecnológicos y sustancias peligrosas", "Fuga de gas"),
        Rule("EFIGAS", A, "4.4 Líneas vitales", "Cerrar la red de gas"),
        Rule("POLICIA", A, "1.5 Evacuación", "Evacuar el perímetro"),
        Rule("CHEC", INF, "4.4 Líneas vitales", "Evitar chispas: cortar energía"),
    ),
    Category.heridos: (
        Rule("CRUZ_ROJA", L, "2.1 Atención prehospitalaria", "Personas heridas"),
        Rule("SEC_SALUD", INF, "2.2 Atención hospitalaria", "Preparar la red hospitalaria"),
    ),
    Category.deslizamiento: (
        Rule("SEC_INFRAESTRUCTURA", L, "4.1 Monitoreo de eventos", "Movimiento en masa"),
        Rule("DEFENSA_CIVIL", A, "1.5 Evacuación", "Evacuar viviendas expuestas"),
        Rule("AGUAS_MANIZALES", INF, "4.4 Líneas vitales", "Revisar tuberías en la ladera"),
    ),
    Category.via_bloqueada: (
        Rule("SEC_INFRAESTRUCTURA", L, "4.3 Manejo de escombros", "Despejar la vía"),
        Rule("POLICIA", A, "1.1 Aislamiento y seguridad", "Desvío y control de tránsito"),
    ),
    Category.dano_estructural: (
        Rule(
            "SEC_INFRAESTRUCTURA",
            L,
            "4.2 Evaluación de daños en edificaciones",
            "Inspección y semáforo",
        ),
    ),
    Category.servicios_caidos: (
        Rule("SEC_INFRAESTRUCTURA", L, "4.4 Líneas vitales", "Servicio público caído"),
    ),
    Category.necesidad_albergue: (
        Rule("SEC_DESARROLLO_SOCIAL", L, "3.2 Alojamiento temporal", "Familias sin vivienda"),
        Rule("CRUZ_ROJA", A, "3.3 Ayuda humanitaria", "Kits y apoyo en albergue"),
    ),
    Category.necesidad_ayuda: (
        Rule("SEC_DESARROLLO_SOCIAL", L, "3.3 Ayuda humanitaria", "Agua, comida o medicamentos"),
        Rule("CRUZ_ROJA", A, "3.3 Ayuda humanitaria", "Distribución de ayudas"),
    ),
    Category.persona_desaparecida: (
        Rule(
            "SEC_DESARROLLO_SOCIAL",
            L,
            "3.1 Registro de población afectada",
            "Registrar y cruzar con el censo",
        ),
        Rule("POLICIA", A, "1.2 Búsqueda y rescate", "Búsqueda de la persona"),
        Rule(
            "CRUZ_ROJA", INF, "3.4 Información comunitaria", "Restablecimiento de contacto familiar"
        ),
    ),
}

# Servicios caídos: la empresa responsable según el texto (sin acentos, en minúsculas).
UTILITY_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AGUAS_MANIZALES", re.compile(r"\b(agua|acueducto|tuberia|alcantarill\w*)\b")),
    ("CHEC", re.compile(r"\b(luz|energia|electric\w*|poste|cables?|transformador)\b")),
    ("EFIGAS", re.compile(r"\b(gas|gasoducto)\b")),
)

LIFE_THREAT_PEOPLE = 5  # con más personas afectadas, el líder envía dos unidades


def _plain(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in norm if not unicodedata.combining(c))


def detect_utilities(texts: Iterable[str]) -> list[str]:
    joined = _plain(" ".join(t for t in texts if t))
    return [code for code, pattern in UTILITY_KEYWORDS if pattern.search(joined)]


def _rules(
    category: Category,
    triage: TriageLevel,
    is_life_threat: bool,
    people: int | None,
    texts: Sequence[str],
) -> tuple[list[Rule], list[str]]:
    rules = list(BASE_RULES.get(category, ()))
    notes: list[str] = []
    severe = triage in (TriageLevel.critico, TriageLevel.alto)

    if category == Category.servicios_caidos:
        utilities = detect_utilities(texts)
        if utilities:
            # La empresa de servicio lidera y la Secretaría queda informada.
            rules = [
                Rule(u, L if i == 0 else A, "4.4 Líneas vitales", "Restablecer el servicio")
                for i, u in enumerate(utilities)
            ]
            rules.append(
                Rule(
                    "SEC_INFRAESTRUCTURA",
                    INF,
                    "4.4 Líneas vitales",
                    "Coordinación de líneas vitales",
                )
            )
        else:
            notes.append("Servicio no identificado en el texto: se informa a las tres empresas")
            rules += [
                Rule(u, INF, "4.4 Líneas vitales", "Servicio sin identificar")
                for u, _ in UTILITY_KEYWORDS
            ]

    if category == Category.heridos and (severe or (people or 0) >= LIFE_THREAT_PEOPLE):
        rules.append(Rule("BOMBEROS", A, "1.2 Búsqueda y rescate", "Heridos graves o múltiples"))
        rules = [
            r if r.agency != "SEC_SALUD" else Rule(r.agency, A, r.task, r.reason) for r in rules
        ]

    if category == Category.deslizamiento and (severe or is_life_threat):
        rules.append(Rule("BOMBEROS", A, "1.2 Búsqueda y rescate", "Deslizamiento sobre viviendas"))

    if category == Category.dano_estructural and severe:
        rules.append(
            Rule("DEFENSA_CIVIL", A, "1.5 Evacuación", "Daño severo: evacuar preventivamente")
        )
        rules.append(Rule("POLICIA", INF, "1.1 Aislamiento y seguridad", "Acordonar el predio"))

    if category == Category.via_bloqueada and severe:
        rules.append(
            Rule(
                "BOMBEROS",
                INF,
                "1.1 Aislamiento y seguridad",
                "Vía crítica hacia hospital o albergue",
            )
        )

    if is_life_threat and (people or 0) > 0 and not any(r.agency == "CRUZ_ROJA" for r in rules):
        rules.append(
            Rule("CRUZ_ROJA", A, "2.1 Atención prehospitalaria", "Personas en riesgo vital")
        )

    return rules, notes


def _dedupe(rules: Sequence[Rule]) -> list[Rule]:
    """Una entrada por agencia, conservando el papel más fuerte."""
    best: dict[str, Rule] = {}
    for rule in rules:
        current = best.get(rule.agency)
        if current is None or ROLE_RANK[rule.role] < ROLE_RANK[current.role]:
            best[rule.agency] = rule
    order = {r.agency: i for i, r in enumerate(rules)}
    return sorted(best.values(), key=lambda r: (ROLE_RANK[r.role], order[r.agency]))


def route_incident(
    *,
    category: Category,
    triage: TriageLevel,
    is_life_threat: bool,
    trust_label: TrustLabel,
    people_affected: int | None = None,
    report_count: int = 1,
    texts: Sequence[str] = (),
) -> Routing:
    """Destinatarios del incidente y si el aviso queda retenido a la espera del PMU."""
    rules, notes = _rules(category, triage, is_life_threat, people_affected, texts)
    recipients = tuple(
        Recipient(r.agency, r.role, AGENCY_FUNCTION[r.agency], r.task, r.reason)
        for r in _dedupe(rules)
    )

    held = trust_label == TrustLabel.posible_falso and not is_life_threat
    hold_reason = (
        "Posible falso: el aviso a las agencias espera la verificación del PMU" if held else None
    )
    if trust_label == TrustLabel.posible_falso and is_life_threat:
        notes.append("Confianza baja, pero hay riesgo vital: se avisa igual (revisión humana)")

    coe_reason: str | None = None
    if triage == TriageLevel.critico or is_life_threat:
        coe_reason = "5.1 Coordinación interinstitucional: incidente crítico"
    elif category == Category.rumor_informacion:
        coe_reason = "5.2 Información pública: rumor que puede requerir desmentido"
    elif not recipients and category != Category.sismo_sentido:
        coe_reason = "5.1 Coordinación: categoría sin agencia asignada, la decide el PMU"

    lead_units = 1
    if is_life_threat and ((people_affected or 0) >= LIFE_THREAT_PEOPLE or report_count >= 5):
        lead_units = 2
        notes.append("Muchas personas o reportes: el líder envía dos unidades")

    return Routing(
        recipients=recipients,
        notify_coe=coe_reason is not None,
        coe_reason=coe_reason,
        held=held,
        hold_reason=hold_reason,
        lead_units=lead_units,
        notes=tuple(notes),
    )


# ------------------------------------------------------------------ plan de despacho


@dataclass(frozen=True)
class Unit:
    """Recurso disponible ya ordenado por cercanía, con su agencia."""

    resource_id: uuid.UUID
    agency: str
    distance_m: float
    eta_min: float
    type: str = ""


# Tipo de recurso preferido según la tarea EMRE (prefijo); si no hay, cualquiera de la agencia.
TASK_RESOURCE: dict[str, tuple[str, ...]] = {
    "1.1": ("patrulla",),
    "1.2": ("cuadrilla_rescate",),
    "1.3": ("maquina_extincion",),
    "1.4": ("maquina_extincion", "cuadrilla_rescate"),
    "1.5": ("patrulla", "cuadrilla_rescate"),
    "2.1": ("ambulancia",),
    "2.2": ("ambulancia",),
    "3.": ("vehiculo_logistico",),
    "4.": ("cuadrilla_tecnica",),
}


def preferred_types(task: str) -> tuple[str, ...]:
    return next((types for prefix, types in TASK_RESOURCE.items() if task.startswith(prefix)), ())


@dataclass(frozen=True)
class PlanLine:
    recipient: Recipient
    unit: Unit | None
    already_dispatched: bool


def build_plan(
    routing: Routing, units: Sequence[Unit], dispatched_agencies: Iterable[str]
) -> list[PlanLine]:
    """Un recurso (el más cercano) por agencia líder o de apoyo que aún no tenga despacho.

    El líder recibe `lead_units` recursos. `units` debe venir ordenado por distancia.
    """
    already = set(dispatched_agencies)
    taken: set[uuid.UUID] = set()
    lines: list[PlanLine] = []
    for recipient in routing.recipients:
        if not recipient.needs_resource:
            continue
        if recipient.agency in already:
            lines.append(PlanLine(recipient, None, True))
            continue
        wanted = routing.lead_units if recipient.role == RecipientRole.lider else 1
        pool = [u for u in units if u.agency == recipient.agency and u.resource_id not in taken]
        preferred = preferred_types(recipient.task)
        # Primero el tipo adecuado a la tarea (más cercano), luego los demás por cercanía.
        pool.sort(key=lambda u: u.type not in preferred)
        if not pool:
            lines.append(PlanLine(recipient, None, False))
            continue
        for unit in pool[:wanted]:
            taken.add(unit.resource_id)
            lines.append(PlanLine(recipient, unit, False))
    return lines
