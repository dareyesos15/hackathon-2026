"""Alertas oficiales con aprobación exclusiva del COE (specs/002 US2, EMRE tarea 5.5).

- Borrador editable por el PMU o el COE; cada edición sube la versión (research R7).
- Solo el COE aprueba (una versión concreta), rechaza o anula, siempre con motivo si rechaza o
  anula (principio III). Toda acción queda en `alert_events`.
- El mensaje se redacta como un reporte (FR-021) y se advierte si trae señales de
  desinformación (FR-022). Área por barrios (unión) o círculo (research R8).
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from geoalchemy2 import WKTElement
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.alert_gateway import AlertGateway
from app.config import get_settings
from app.core.nlp import misinformation_signals
from app.core.privacy import redact
from app.core.text import normalize
from app.domain import AlertAction, AlertChannel, AlertStatus, AlertType, Role
from app.models import Alert, AlertDelivery, AlertEvent

SMS_MAX = 160
RADIUS_MIN_M, RADIUS_MAX_M = 100.0, 3000.0
CIRCLE_SEGMENTS = 32  # 32 lados (research R8): quad_segs = 8
EDITORS = frozenset({Role.operador_pmu, Role.coe})


class AlertError(Exception):
    def __init__(
        self, code: str, message: str, status: int, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


# ------------------------------------------------------------------------ área


@lru_cache
def barrio_shapes() -> dict[str, BaseGeometry]:
    path = get_settings().data_dir / "geo" / "barrios.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["properties"]["name"]: shape(f["geometry"]) for f in data["features"]}


@lru_cache
def urban_area() -> BaseGeometry:
    return unary_union(list(barrio_shapes().values()))


def circle(lat: float, lon: float, radius_m: float) -> Polygon:
    """Polígono de 32 lados; metros → grados con escala local por cos(lat)."""
    unit = Point(lon, lat).buffer(1.0, quad_segs=CIRCLE_SEGMENTS // 4)
    sx = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    sy = radius_m / 110_540.0
    scaled = affinity.scale(unit, xfact=sx, yfact=sy, origin=(lon, lat))
    assert isinstance(scaled, Polygon)
    return scaled


def _multi(geom: BaseGeometry) -> MultiPolygon:
    if isinstance(geom, MultiPolygon):
        return geom
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return MultiPolygon(polys)


@dataclass(frozen=True)
class AreaSpec:
    barrios: tuple[str, ...] = ()
    lat: float | None = None
    lon: float | None = None
    radius_m: float | None = None


def build_area(spec: AreaSpec) -> tuple[MultiPolygon, list[str], dict[str, float] | None]:
    if spec.barrios:
        known = barrio_shapes()
        missing = [b for b in spec.barrios if b not in known]
        if missing:
            raise AlertError("unknown_barrio", f"Barrio desconocido: {', '.join(missing)}", 422)
        geom = _multi(unary_union([known[b] for b in spec.barrios]))
        return geom, list(dict.fromkeys(spec.barrios)), None
    if spec.lat is None or spec.lon is None or spec.radius_m is None:
        raise AlertError("area_required", "Defina el área: barrios o un círculo en el mapa", 422)
    if not RADIUS_MIN_M <= spec.radius_m <= RADIUS_MAX_M:
        raise AlertError(
            "invalid_radius", f"El radio debe estar entre {RADIUS_MIN_M:.0f} y 3.000 m", 422
        )
    geom = _multi(circle(spec.lat, spec.lon, spec.radius_m))
    if not geom.intersects(urban_area()):
        raise AlertError("out_of_area", "El área está fuera del casco urbano de Manizales", 422)
    return geom, [], {"lat": spec.lat, "lon": spec.lon, "radius_m": spec.radius_m}


# ------------------------------------------------------------------------ mensaje


def clean_message(message: str, channels: Sequence[str]) -> tuple[str, list[str]]:
    """Mensaje redactado y señales de desinformación. Valida el largo para SMS."""
    text = message.strip()
    if not text:
        raise AlertError("message_required", "Escriba el mensaje de la alerta", 422)
    redacted = redact(text).text
    if AlertChannel.sms_cuadrillas in channels and len(redacted) > SMS_MAX:
        raise AlertError(
            "sms_too_long",
            f"Para SMS el mensaje debe tener máximo {SMS_MAX} caracteres ({len(redacted)})",
            422,
        )
    return redacted, misinformation_signals(normalize(text))


def check_channels(channels: Sequence[str]) -> list[str]:
    unique = list(dict.fromkeys(channels))
    if not unique:
        raise AlertError("channels_required", "Elija al menos un canal", 422)
    return unique


# ------------------------------------------------------------------------ ciclo de vida


def _event(
    alert: Alert, actor: Role, action: AlertAction, payload: dict[str, Any] | None = None
) -> AlertEvent:
    return AlertEvent(
        alert_id=alert.id,
        actor_role=actor,
        action=action,
        alert_version=alert.version,
        payload={k: v for k, v in (payload or {}).items() if v is not None},
        source="tablero PMU",
    )


def _require_editor(actor: Role) -> None:
    if actor not in EDITORS:
        raise AlertError("forbidden", "Solo el PMU o el COE redactan alertas", 403)


def _require_coe(actor: Role) -> None:
    if actor != Role.coe:
        raise AlertError("coe_only", "Solo el COE puede aprobar alertas oficiales", 403)


def _misinfo_gate(signals: list[str], confirmed: bool) -> None:
    if signals and not confirmed:
        raise AlertError(
            "misinformation_confirmation_required",
            "El mensaje tiene señales de desinformación; corríjalo o confirme que es correcto",
            422,
            {"signals": signals},
        )


async def create_alert(
    session: AsyncSession,
    *,
    type_: AlertType,
    area: AreaSpec,
    message: str,
    channels: Sequence[str],
    origin_incident_id: uuid.UUID | None,
    origin_manzana_id: str | None,
    confirm_misinformation: bool,
    actor: Role,
) -> Alert:
    _require_editor(actor)
    chans = check_channels(channels)
    text, signals = clean_message(message, chans)
    _misinfo_gate(signals, confirm_misinformation)
    geom, barrios, circ = build_area(area)
    alert = Alert(
        type=type_,
        status=AlertStatus.borrador,
        area=WKTElement(geom.wkt, srid=4326),
        area_barrios=barrios,
        area_circle=circ,
        message=text,
        channels=chans,
        misinfo_signals=signals,
        origin_incident_id=origin_incident_id,
        origin_manzana_id=origin_manzana_id,
        created_by_role=actor,
        source="tablero PMU",
        version=1,
    )
    session.add(alert)
    await session.flush()
    session.add(_event(alert, actor, AlertAction.crear, {"tipo": type_.value}))
    if signals:
        session.add(
            _event(alert, actor, AlertAction.confirmar_desinformacion, {"senales": signals})
        )
    await session.commit()
    await session.refresh(alert)
    return alert


def _check_version(alert: Alert, version: int) -> None:
    if alert.version != version:
        raise AlertError(
            "version_conflict",
            f"El borrador cambió (versión {alert.version}); revise la versión nueva",
            409,
            {"current_version": alert.version},
        )


async def update_alert(
    session: AsyncSession,
    alert: Alert,
    *,
    version: int,
    type_: AlertType | None,
    area: AreaSpec | None,
    message: str | None,
    channels: Sequence[str] | None,
    confirm_misinformation: bool,
    actor: Role,
) -> Alert:
    _require_editor(actor)
    if alert.status != AlertStatus.borrador:
        raise AlertError("not_editable", "Solo se edita un borrador", 409)
    _check_version(alert, version)
    chans = check_channels(channels) if channels is not None else list(alert.channels)
    text, signals = clean_message(message if message is not None else alert.message, chans)
    if message is not None:
        _misinfo_gate(signals, confirm_misinformation)
    changes: list[str] = []
    if type_ is not None and type_ != alert.type:
        alert.type = type_
        changes.append("tipo")
    if area is not None:
        geom, barrios, circ = build_area(area)
        alert.area = WKTElement(geom.wkt, srid=4326)
        alert.area_barrios = barrios
        alert.area_circle = circ
        changes.append("area")
    if message is not None and text != alert.message:
        alert.message = text
        alert.misinfo_signals = signals
        changes.append("mensaje")
    if channels is not None and chans != list(alert.channels):
        alert.channels = chans
        changes.append("canales")
    alert.version += 1
    session.add(_event(alert, actor, AlertAction.editar, {"cambios": changes}))
    if message is not None and signals:
        session.add(
            _event(alert, actor, AlertAction.confirmar_desinformacion, {"senales": signals})
        )
    await session.commit()
    await session.refresh(alert)
    return alert


async def approve_alert(
    session: AsyncSession,
    alert: Alert,
    *,
    version: int,
    actor: Role,
    gateway: AlertGateway,
    now: datetime,
) -> list[AlertDelivery]:
    _require_coe(actor)
    if alert.status != AlertStatus.borrador:
        raise AlertError("not_pending", "La alerta no está pendiente de aprobación", 409)
    if alert.version != version:
        session.add(
            _event(alert, actor, AlertAction.aprobacion_conflicto, {"version_vista": version})
        )
        await session.commit()
        _check_version(alert, version)
    alert.status = AlertStatus.emitida
    alert.approved_by_role = actor
    alert.emitted_at = now
    session.add(_event(alert, actor, AlertAction.aprobar))
    await session.flush()
    deliveries = await gateway.deliver(session, alert, now)
    await session.commit()
    await session.refresh(alert)
    return deliveries


async def reject_alert(
    session: AsyncSession,
    alert: Alert,
    *,
    version: int,
    reason: str | None,
    actor: Role,
    now: datetime,
) -> Alert:
    _require_coe(actor)
    if alert.status != AlertStatus.borrador:
        raise AlertError("not_pending", "La alerta no está pendiente de aprobación", 409)
    _check_version(alert, version)
    clean = _reason(reason)
    alert.status = AlertStatus.rechazada
    alert.closed_at = now
    alert.close_reason = clean
    session.add(_event(alert, actor, AlertAction.rechazar, {"motivo": clean}))
    await session.commit()
    await session.refresh(alert)
    return alert


async def cancel_alert(
    session: AsyncSession, alert: Alert, *, reason: str | None, actor: Role, now: datetime
) -> Alert:
    _require_coe(actor)
    if alert.status != AlertStatus.emitida:
        raise AlertError("not_emitted", "Solo se anula una alerta emitida", 409)
    clean = _reason(reason)
    alert.status = AlertStatus.anulada
    alert.closed_at = now
    alert.close_reason = clean
    session.add(_event(alert, actor, AlertAction.anular, {"motivo": clean}))
    await session.commit()
    await session.refresh(alert)
    return alert


def _reason(reason: str | None) -> str:
    if not reason or not reason.strip():
        raise AlertError("reason_required", "Escriba el motivo", 422)
    return redact(reason.strip()).text
