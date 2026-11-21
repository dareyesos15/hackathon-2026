"""Despacho a agencias y trazabilidad de recursos (specs/002 US1).

- Sugerencia por la tabla de funciones de respuesta de la EMRE (research R2, FR-001).
- Invariantes en la base: un despacho activo por recurso (índice único parcial) y sin doble
  despacho del incidente salvo refuerzo justificado (bloqueo de la fila del incidente, R3).
- Puntos de paso tipo RFID: la posición actual es la del punto con mayor hora (FR-008).
- Toda acción humana queda en `report_events` (principio III). Nada aquí cierra incidentes.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.routing import RoutingProvider
from app.core.geo import in_manizales
from app.core.privacy import redact
from app.core.recipients import PlanLine, Routing, Unit, build_plan, route_incident
from app.domain import (
    ACTIVE_DISPATCH,
    Category,
    DispatchStatus,
    EmreFunction,
    IncidentStatus,
    ReportAction,
    ResourceStatus,
    Role,
    TrackKind,
    TrackOrigin,
)
from app.models import (
    Agency,
    Dispatch,
    Incident,
    Report,
    ReportEvent,
    Resource,
    ResourceTrack,
)

_SALVAMENTO = ("BOMBEROS", "DEFENSA_CIVIL", "POLICIA")
_SALUD = ("CRUZ_ROJA", "SEC_SALUD")
_SOCIAL = ("SEC_DESARROLLO_SOCIAL", "CRUZ_ROJA")
_INFRA = ("SEC_INFRAESTRUCTURA", "AGUAS_MANIZALES", "CHEC", "EFIGAS")

# CLAUDE.md §7.7 / FR-001. La primera agencia es la sugerida; las demás, alternativas.
EMRE_ROUTING: dict[Category, tuple[EmreFunction, tuple[str, ...]]] = {
    Category.personas_atrapadas: (EmreFunction.salvamento_seguridad, _SALVAMENTO),
    Category.incendio: (EmreFunction.salvamento_seguridad, _SALVAMENTO),
    Category.fuga_gas: (EmreFunction.salvamento_seguridad, _SALVAMENTO),
    Category.colapso_estructura: (EmreFunction.salvamento_seguridad, _SALVAMENTO),
    Category.heridos: (EmreFunction.salud_saneamiento, _SALUD),
    Category.necesidad_albergue: (EmreFunction.asistencia_social, _SOCIAL),
    Category.necesidad_ayuda: (EmreFunction.asistencia_social, _SOCIAL),
    Category.persona_desaparecida: (EmreFunction.asistencia_social, _SOCIAL),
    Category.dano_estructural: (EmreFunction.infraestructura_servicios, _INFRA),
    Category.via_bloqueada: (EmreFunction.infraestructura_servicios, _INFRA),
    Category.servicios_caidos: (EmreFunction.infraestructura_servicios, _INFRA),
    Category.deslizamiento: (EmreFunction.infraestructura_servicios, _INFRA),
}

CLOSED_INCIDENT = frozenset({IncidentStatus.descartado, IncidentStatus.atendido})

# acción → (estados de origen permitidos, estado destino)
DISPATCH_TRANSITIONS: dict[str, tuple[frozenset[DispatchStatus], DispatchStatus]] = {
    "llegada": (frozenset({DispatchStatus.en_camino}), DispatchStatus.en_sitio),
    "finalizar": (frozenset({DispatchStatus.en_sitio}), DispatchStatus.finalizado),
    "cancelar": (ACTIVE_DISPATCH, DispatchStatus.cancelado),
    "fuera_de_servicio": (ACTIVE_DISPATCH, DispatchStatus.cancelado),
}
ACTION_ROLES: dict[str, frozenset[Role]] = {
    "llegada": frozenset({Role.agencia, Role.operador_pmu, Role.coe}),
    "finalizar": frozenset({Role.agencia, Role.operador_pmu, Role.coe}),
    "cancelar": frozenset({Role.operador_pmu, Role.coe}),
    "fuera_de_servicio": frozenset({Role.agencia, Role.operador_pmu, Role.coe}),
}
NOTE_REQUIRED = frozenset({"cancelar", "fuera_de_servicio"})
RESOURCE_AFTER: dict[str, ResourceStatus] = {
    "llegada": ResourceStatus.en_sitio,
    "finalizar": ResourceStatus.disponible,
    "cancelar": ResourceStatus.disponible,
    "fuera_de_servicio": ResourceStatus.fuera_de_servicio,
}
CHECKPOINT_FRACTIONS: tuple[tuple[str, float], ...] = (
    ("control", 1 / 3),
    ("control", 2 / 3),
    ("llegada", 1.0),
)


class DispatchError(Exception):
    def __init__(
        self, code: str, message: str, status: int, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


# ------------------------------------------------------------------------ reglas puras


def routing_for(category: Category) -> tuple[EmreFunction | None, tuple[str, ...]]:
    """Función EMRE y agencias (sugerida primero). Sin función: `(None, ())`."""
    entry = EMRE_ROUTING.get(category)
    return entry if entry else (None, ())


@dataclass(frozen=True)
class ResourceView:
    id: Any
    code: str
    agency_code: str
    lat: float
    lon: float
    status: ResourceStatus


@dataclass(frozen=True)
class RankedCandidate:
    resource: ResourceView
    distance_m: float
    eta_min: float


def rank_candidates(
    lat: float,
    lon: float,
    resources: Sequence[ResourceView],
    agencies: tuple[str, ...],
    routing: RoutingProvider,
) -> tuple[list[RankedCandidate], bool]:
    """Recursos disponibles de la agencia sugerida por cercanía; si no hay, los alternativos."""

    def ranked(pool: list[ResourceView]) -> list[RankedCandidate]:
        out = []
        for r in pool:
            route = routing.estimate(r.lat, r.lon, lat, lon)
            out.append(RankedCandidate(r, route.distance_m, route.duration_s / 60))
        return sorted(out, key=lambda c: c.distance_m)

    available = [r for r in resources if r.status == ResourceStatus.disponible]
    if not agencies:
        return ranked(available), False
    main = [r for r in available if r.agency_code == agencies[0]]
    if main:
        return ranked(main), False
    return ranked([r for r in available if r.agency_code in agencies[1:]]), True


def next_status(
    current: DispatchStatus, action: str, actor: Role, note: str | None = None
) -> DispatchStatus:
    if action not in DISPATCH_TRANSITIONS:
        raise DispatchError("invalid_action", f"Acción desconocida: {action}", 422)
    if actor not in ACTION_ROLES[action]:
        raise DispatchError("forbidden", "Su rol no puede ejecutar esta acción", 403)
    allowed, target = DISPATCH_TRANSITIONS[action]
    if current not in allowed:
        raise DispatchError(
            "invalid_transition",
            f"No se puede aplicar «{action}» a un despacho en estado {current.value}",
            409,
        )
    if action in NOTE_REQUIRED and not (note and note.strip()):
        raise DispatchError("note_required", "Escriba el motivo", 422)
    return target


def resource_status_after(action: str) -> ResourceStatus:
    return RESOURCE_AFTER[action]


def should_move(last_seen_at: datetime | None, at: datetime) -> bool:
    """La posición actual es la del punto de paso más reciente por hora, no por llegada."""
    return last_seen_at is None or at > last_seen_at


def planned_checkpoints(
    start: datetime, eta_at: datetime, speedup: float
) -> list[tuple[str, float, datetime]]:
    """Puntos de control y llegada del avance SIMULADO, con el tiempo comprimido `speedup`×."""
    total = (eta_at - start) / max(speedup, 1e-6)
    return [(kind, f, start + total * f) for kind, f in CHECKPOINT_FRACTIONS]


def interpolate(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def _clean(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    return redact(text.strip()).text


def _point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


# ------------------------------------------------------------------------ base de datos


async def resource_views(
    session: AsyncSession, resources: Sequence[Resource] | None = None
) -> list[ResourceView]:
    stmt = select(
        Resource.id,
        Resource.code,
        Agency.code,
        func.ST_Y(Resource.last_geom),
        func.ST_X(Resource.last_geom),
        Resource.status,
    ).join(Agency, Agency.id == Resource.agency_id)
    if resources is not None:
        stmt = stmt.where(Resource.id.in_([r.id for r in resources]))
    rows = (await session.execute(stmt)).all()
    return [ResourceView(rid, code, ac, lat, lon, st) for rid, code, ac, lat, lon, st in rows]


async def incident_point(session: AsyncSession, incident: Incident) -> tuple[float, float] | None:
    row = (
        await session.execute(
            select(func.ST_Y(Incident.centroid), func.ST_X(Incident.centroid)).where(
                Incident.id == incident.id
            )
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return float(row[0]), float(row[1])


@dataclass
class Suggestion:
    emre_function: EmreFunction | None
    suggested_agency: Agency | None
    alternatives: list[Agency]
    candidates: list[RankedCandidate]
    fallback_used: bool


async def suggest(
    session: AsyncSession,
    incident: Incident,
    routing: RoutingProvider,
    recipients: Routing | None = None,
) -> Suggestion:
    function, codes = routing_for(incident.category)
    lead = recipients.lead if recipients else None
    if lead is not None and (not codes or lead.agency != codes[0]):
        # El líder del plan (p. ej. la empresa de servicio identificada) va primero.
        function = lead.emre_function
        codes = (lead.agency, *(c for c in codes if c != lead.agency))
    agencies = {a.code: a for a in (await session.execute(select(Agency))).scalars()}
    point = await incident_point(session, incident)
    candidates: list[RankedCandidate] = []
    fallback = False
    if point is not None:
        candidates, fallback = rank_candidates(
            point[0], point[1], await resource_views(session), codes, routing
        )
    return Suggestion(
        emre_function=function,
        suggested_agency=agencies.get(codes[0]) if codes else None,
        alternatives=[agencies[c] for c in codes[1:] if c in agencies],
        candidates=candidates,
        fallback_used=fallback,
    )


async def incident_texts(session: AsyncSession, incident_id: uuid.UUID) -> list[str]:
    """Texto ya redactado de los reportes del incidente (para identificar el servicio)."""
    rows = await session.execute(
        select(Report.text_redacted).where(Report.incident_id == incident_id).limit(50)
    )
    return [t for (t,) in rows if t]


def routing_of(incident: Incident, texts: Sequence[str]) -> Routing:
    return route_incident(
        category=incident.category,
        triage=incident.triage_level,
        is_life_threat=incident.is_life_threat,
        trust_label=incident.trust_label,
        people_affected=incident.people_affected,
        report_count=incident.report_count,
        texts=texts,
    )


async def incident_routing(session: AsyncSession, incident: Incident) -> Routing:
    return routing_of(incident, await incident_texts(session, incident.id))


async def active_agency_codes(session: AsyncSession, incident_id: uuid.UUID) -> set[str]:
    rows = await session.execute(
        select(Agency.code)
        .join(Dispatch, Dispatch.agency_id == Agency.id)
        .where(Dispatch.incident_id == incident_id, Dispatch.status.in_(list(ACTIVE_DISPATCH)))
    )
    return {code for (code,) in rows}


async def dispatch_plan(
    session: AsyncSession, incident: Incident, routing: RoutingProvider, recipients: Routing
) -> list[PlanLine]:
    """Recurso más cercano por agencia líder y de apoyo sin despacho activo (propuesta)."""
    point = await incident_point(session, incident)
    if point is None:
        return []
    types = dict((await session.execute(select(Resource.id, Resource.type))).tuples().all())
    units = []
    for view in await resource_views(session):
        if view.status != ResourceStatus.disponible:
            continue
        route = routing.estimate(view.lat, view.lon, point[0], point[1])
        units.append(
            Unit(
                view.id,
                view.agency_code,
                route.distance_m,
                route.duration_s / 60,
                types[view.id].value,
            )
        )
    units.sort(key=lambda u: u.distance_m)
    return build_plan(recipients, units, await active_agency_codes(session, incident.id))


async def execute_plan(
    session: AsyncSession,
    *,
    client_uuid: uuid.UUID,
    incident: Incident,
    resource_ids: Sequence[uuid.UUID] | None,
    actor: Role,
    routing: RoutingProvider,
    now: datetime,
) -> CreateResult:
    """Despacha el plan multiagencia (o los recursos elegidos de él) en una sola confirmación.

    Si el incidente ya tiene un despacho activo, los nuevos recursos entran como refuerzo con
    una justificación automática que nombra las agencias que completan el plan.
    """
    all_ids = list((await session.execute(select(Resource.id))).scalars())
    derived = [_uuid_for(client_uuid, rid) for rid in all_ids]
    repeated = list(
        (await session.execute(select(Dispatch).where(Dispatch.client_uuid.in_(derived)))).scalars()
    )
    if repeated:  # misma confirmación del plan (idempotencia, FR-007)
        return CreateResult(repeated, False, incident)
    recipients = await incident_routing(session, incident)
    lines = await dispatch_plan(session, incident, routing, recipients)
    planned = [line.unit.resource_id for line in lines if line.unit is not None]
    ids = list(resource_ids) if resource_ids else planned
    if not ids:
        raise DispatchError(
            "empty_plan", "El plan no tiene recursos disponibles para despachar", 422
        )
    has_active = bool(await active_agency_codes(session, incident.id))
    agencies = sorted({line.recipient.agency for line in lines if line.unit is not None})
    justification = (
        "Completa el plan multiagencia EMRE: " + ", ".join(agencies) if has_active else None
    )
    return await create_dispatches(
        session,
        client_uuid=client_uuid,
        incident_id=incident.id,
        resource_ids=ids,
        is_reinforcement=has_active,
        justification=justification,
        actor=actor,
        routing=routing,
        now=now,
    )


def _event(
    incident_id: uuid.UUID, actor: Role, action: ReportAction, payload: dict[str, Any]
) -> ReportEvent:
    return ReportEvent(
        incident_id=incident_id,
        actor_role=actor,
        action=action,
        payload={k: v for k, v in payload.items() if v is not None},
        source="despacho",
    )


@dataclass
class CreateResult:
    dispatches: list[Dispatch]
    created: bool
    incident: Incident


def _uuid_for(client_uuid: uuid.UUID, resource_id: uuid.UUID) -> uuid.UUID:
    """Un `client_uuid` por despacho (uno por recurso) derivado del de la petición."""
    return uuid.uuid5(client_uuid, str(resource_id))


async def create_dispatches(
    session: AsyncSession,
    *,
    client_uuid: uuid.UUID,
    incident_id: uuid.UUID,
    resource_ids: Sequence[uuid.UUID],
    is_reinforcement: bool,
    justification: str | None,
    actor: Role,
    routing: RoutingProvider,
    now: datetime,
) -> CreateResult:
    if actor not in (Role.operador_pmu, Role.coe):
        raise DispatchError("forbidden", "Solo el PMU o el COE despachan recursos", 403)
    ids = list(dict.fromkeys(resource_ids))
    if not ids:
        raise DispatchError("resources_required", "Elija al menos un recurso", 422)

    derived = [_uuid_for(client_uuid, rid) for rid in ids]
    existing = list(
        (await session.execute(select(Dispatch).where(Dispatch.client_uuid.in_(derived)))).scalars()
    )
    if existing:  # misma confirmación repetida (FR-007)
        incident = await session.get(Incident, existing[0].incident_id)
        assert incident is not None
        return CreateResult(existing, False, incident)

    incident = (
        await session.execute(select(Incident).where(Incident.id == incident_id).with_for_update())
    ).scalar_one_or_none()
    if incident is None:
        raise DispatchError("not_found", "Incidente no existe", 404)
    if incident.status in CLOSED_INCIDENT:
        raise DispatchError(
            "incident_closed", f"El incidente está {incident.status.value}; no se despacha", 422
        )
    reason = _clean(justification)
    if is_reinforcement and not reason:
        raise DispatchError("justification_required", "Un refuerzo requiere justificación", 422)

    active = list(
        (
            await session.execute(
                select(Dispatch).where(
                    Dispatch.incident_id == incident.id,
                    Dispatch.status.in_(list(ACTIVE_DISPATCH)),
                )
            )
        ).scalars()
    )
    if active and not is_reinforcement:
        session.add(
            _event(
                incident.id,
                actor,
                ReportAction.despacho_doble_bloqueado,
                {"despachos_activos": [str(d.id) for d in active]},
            )
        )
        await session.commit()
        raise DispatchError(
            "active_dispatch_exists",
            "El incidente ya tiene un despacho activo; márquelo como refuerzo y justifíquelo",
            409,
            {"active": active},
        )

    point = await incident_point(session, incident)
    if point is None:
        raise DispatchError("incident_without_location", "El incidente no tiene ubicación", 422)

    resources = list(
        (
            await session.execute(select(Resource).where(Resource.id.in_(ids)).with_for_update())
        ).scalars()
    )
    if len(resources) != len(ids):
        raise DispatchError("not_found", "Algún recurso no existe", 404)
    busy = [str(r.id) for r in resources if r.status != ResourceStatus.disponible]
    if busy:
        raise DispatchError(
            "resource_unavailable", "Algún recurso no está disponible", 409, {"resource_ids": busy}
        )

    function, codes = routing_for(incident.category)
    agencies = {a.id: a for a in (await session.execute(select(Agency))).scalars()}
    views = {v.id: v for v in await resource_views(session, resources)}
    order = {rid: i for i, rid in enumerate(ids)}
    created: list[Dispatch] = []
    for resource in sorted(resources, key=lambda r: order[r.id]):
        view = views[resource.id]
        route = routing.estimate(view.lat, view.lon, point[0], point[1])
        agency = agencies[resource.agency_id]
        dispatch = Dispatch(
            client_uuid=_uuid_for(client_uuid, resource.id),
            incident_id=incident.id,
            resource_id=resource.id,
            agency_id=agency.id,
            emre_function=function,
            suggested=bool(codes) and agency.code == codes[0],
            is_reinforcement=is_reinforcement,
            justification=reason,
            status=DispatchStatus.en_camino,
            eta_at=now + timedelta(seconds=route.duration_s),
            distance_m=round(route.distance_m),
            created_by_role=actor,
            source="SIMULADO",
        )
        session.add(dispatch)
        await session.flush()
        resource.status = ResourceStatus.en_camino
        session.add(
            ResourceTrack(
                resource_id=resource.id,
                dispatch_id=dispatch.id,
                kind=TrackKind.salida,
                origin=TrackOrigin.rfid_simulado,
                geom=_point(view.lat, view.lon),
                at=now,
                source="SIMULADO",
            )
        )
        resource.last_seen_at = now
        session.add(
            _event(
                incident.id,
                actor,
                ReportAction.reforzar if is_reinforcement else ReportAction.despachar,
                {
                    "despacho": str(dispatch.id),
                    "recurso": resource.code,
                    "agencia": agency.code,
                    "sugerida": dispatch.suggested,
                    "justificacion": reason,
                },
            )
        )
        created.append(dispatch)
    await session.commit()
    return CreateResult(created, True, incident)


async def _resource_point(
    session: AsyncSession, resource: Resource, base: bool
) -> tuple[float, float]:
    column = Resource.base_geom if base else Resource.last_geom
    lat, lon = (
        await session.execute(
            select(func.ST_Y(column), func.ST_X(column)).where(Resource.id == resource.id)
        )
    ).one()
    return float(lat), float(lon)


@dataclass
class TrackResult:
    track: ResourceTrack
    resource: Resource
    dispatch: Dispatch | None = None
    moved: bool = False
    extra_events: list[str] = field(default_factory=list)


async def record_track(
    session: AsyncSession,
    resource: Resource,
    *,
    kind: TrackKind,
    origin: TrackOrigin,
    lat: float,
    lon: float,
    at: datetime,
    actor: Role,
    commit: bool = True,
) -> TrackResult:
    """Registra un punto de paso; `llegada` pasa el despacho en camino a `en_sitio`."""
    if not in_manizales(lat, lon):
        raise DispatchError("out_of_area", "El punto está fuera de Manizales", 422)
    dispatch = (
        await session.execute(
            select(Dispatch)
            .where(
                Dispatch.resource_id == resource.id,
                Dispatch.status.in_(list(ACTIVE_DISPATCH)),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    track = ResourceTrack(
        resource_id=resource.id,
        dispatch_id=dispatch.id if dispatch else None,
        kind=kind,
        origin=origin,
        geom=_point(lat, lon),
        at=at,
        source="SIMULADO" if origin == TrackOrigin.rfid_simulado else "manual",
    )
    session.add(track)
    moved = should_move(resource.last_seen_at, at)
    if moved:
        resource.last_geom = _point(lat, lon)
        resource.last_seen_at = at
    changed = None
    if kind == TrackKind.llegada and dispatch and dispatch.status == DispatchStatus.en_camino:
        dispatch.status = DispatchStatus.en_sitio
        dispatch.arrived_at = at
        resource.status = ResourceStatus.en_sitio
        session.add(
            _event(
                dispatch.incident_id,
                actor,
                ReportAction.despacho_estado,
                {"despacho": str(dispatch.id), "estado": "en_sitio", "origen": origin.value},
            )
        )
        changed = dispatch
    await session.flush()
    if commit:
        await session.commit()
    return TrackResult(track, resource, changed, moved)


async def update_dispatch(
    session: AsyncSession,
    dispatch: Dispatch,
    *,
    action: str,
    actor: Role,
    note: str | None,
    now: datetime,
) -> Dispatch:
    target = next_status(dispatch.status, action, actor, note)
    resource = (
        await session.execute(
            select(Resource).where(Resource.id == dispatch.resource_id).with_for_update()
        )
    ).scalar_one()
    clean = _clean(note)
    if action == "llegada":
        incident = await session.get(Incident, dispatch.incident_id)
        point = await incident_point(session, incident) if incident else None
        if point is None:
            point = await _resource_point(session, resource, base=False)
        await record_track(
            session,
            resource,
            kind=TrackKind.llegada,
            origin=TrackOrigin.manual,
            lat=point[0],
            lon=point[1],
            at=now,
            actor=actor,
            commit=False,
        )
        await session.commit()
        return dispatch

    dispatch.status = target
    dispatch.closed_at = now
    if clean:
        dispatch.close_note = clean
    resource.status = resource_status_after(action)
    base = await _resource_point(session, resource, base=True)
    session.add(
        ResourceTrack(
            resource_id=resource.id,
            dispatch_id=dispatch.id,
            kind=TrackKind.regreso,
            origin=TrackOrigin.manual,
            geom=_point(*base),
            at=now,
            source="SIMULADO",
        )
    )
    resource.last_geom = _point(*base)
    resource.last_seen_at = now
    session.add(
        _event(
            dispatch.incident_id,
            actor,
            ReportAction.cancelar_despacho
            if target == DispatchStatus.cancelado
            else (ReportAction.despacho_estado),
            {"despacho": str(dispatch.id), "estado": target.value, "accion": action, "nota": clean},
        )
    )
    await session.commit()
    return dispatch
