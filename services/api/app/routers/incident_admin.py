"""Gestión de incidentes (PMU/COE): crear a mano y asignar o desacoplar de alertas masivas."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.auth import require_role
from app.core.manual_incident import ManualIncident, create_manual_incident
from app.core.mass_alert import MassAlertError, assign_incidents
from app.core.pipeline import Engine
from app.db import get_session
from app.domain import Role
from app.mass_alert_schemas import IncidentAssignIn, ManualIncidentIn
from app.routers.ingest import get_engine
from app.routers.mass_alerts import http_error, publish_progress
from app.schemas import IncidentList, IncidentSummary
from app.serializers import incidents_out

router = APIRouter(prefix="/incidents", tags=["gestión de incidentes"])

EDITORS = (Role.operador_pmu, Role.coe)


@router.post("", response_model=IncidentSummary, status_code=status.HTTP_201_CREATED)
async def post_incident(
    body: ManualIncidentIn,
    role: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
    engine: Engine = Depends(get_engine),
) -> IncidentSummary:
    """Crea un incidente sin reportes ciudadanos (p. ej. informado por radio). Nace verificado
    porque lo registra una persona; queda en la bitácora como `crear_manual`."""
    try:
        incident = await create_manual_incident(
            session,
            engine,
            ManualIncident(
                category=body.category,
                description=body.description,
                triage_level=body.triage_level,
                barrio=body.barrio,
                lat=body.lat,
                lon=body.lon,
                people_affected=body.people_affected,
                mass_alert_id=body.mass_alert_id,
            ),
            role,
        )
    except MassAlertError as err:
        await session.rollback()
        raise http_error(err) from err
    summary = (await incidents_out(session, [incident]))[0]
    bus.publish("incident.upserted", summary.model_dump(mode="json"))
    bus.publish("kpi.updated", {})
    publish_progress([incident.mass_alert_id])
    return summary


@router.post("/assign", response_model=IncidentList)
async def post_assign(
    body: IncidentAssignIn,
    role: Role = Depends(require_role(*EDITORS)),
    session: AsyncSession = Depends(get_session),
) -> IncidentList:
    """Asigna incidentes a una alerta masiva activa o los desacopla a la operación ordinaria."""
    try:
        incidents = await assign_incidents(session, body.incident_ids, body.mass_alert_id, role)
    except MassAlertError as err:
        await session.rollback()
        raise http_error(err) from err
    items = await incidents_out(session, incidents)
    for item in items:
        bus.publish("incident.upserted", item.model_dump(mode="json"))
    # Progreso de origen y destino, y el conteo de la bandeja "sin asignar".
    bus.publish("mass_alert.changed", {"status": "asignacion"})
    return IncidentList(items=items, cutoff_at=datetime.now(UTC))
