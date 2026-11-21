"""Procesamiento del dispositivo de monitoreo de zonas inseguras (patente NC2025/0015763).

Funciones puras: reproducen lo que hace la unidad principal (100) con sus sensores ultrasónico e
infrarrojo dentro del espacio cónico configurado, y el módulo RFID (300) que reconoce al personal
autorizado. El mismo código procesa lecturas simuladas y las de un dispositivo real.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain import ZoneDetector, ZoneEventKind

LOW_BATTERY_PCT = 15
# Radio y ventana en que una intrusión corrobora un incidente estructural (señal de 10 pts).
CONFIRM_RADIUS_M = 150.0
CONFIRM_WINDOW_H = 3.0
CONFIRMABLE_CATEGORIES = frozenset({"personas_atrapadas", "colapso_estructura", "dano_estructural"})


@dataclass(frozen=True)
class Cone:
    """Espacio cónico configurado desde la unidad de configuración (200)."""

    range_m: float
    half_angle_deg: float


@dataclass(frozen=True)
class Reading:
    """Lectura cruda del dispositivo.

    `ultrasonic_m`: distancia del eco ultrasónico (None si no hubo eco).
    `infrared`: presencia térmica detectada por el sensor infrarrojo.
    `bearing_deg`: ángulo del objetivo respecto al eje del cono (0 = al frente).
    """

    ultrasonic_m: float | None
    infrared: bool
    bearing_deg: float
    rfid_tag: str | None
    battery_pct: int
    tamper: bool = False


@dataclass(frozen=True)
class Classified:
    kind: ZoneEventKind
    detector: ZoneDetector | None
    distance_m: float | None
    authorized: bool


def in_cone(distance_m: float, bearing_deg: float, cone: Cone) -> bool:
    return 0 <= distance_m <= cone.range_m and abs(bearing_deg) <= cone.half_angle_deg


def classify(reading: Reading, cone: Cone, authorized_tags: frozenset[str]) -> list[Classified]:
    """Eventos que genera una lectura (puede ser ninguno, p. ej. un objetivo fuera del cono)."""
    events: list[Classified] = []
    if reading.tamper:
        events.append(Classified(ZoneEventKind.manipulacion, None, None, False))
    if reading.battery_pct < LOW_BATTERY_PCT:
        events.append(Classified(ZoneEventKind.bateria_baja, None, None, False))

    ultra = reading.ultrasonic_m is not None and in_cone(
        reading.ultrasonic_m, reading.bearing_deg, cone
    )
    infra = reading.infrared and abs(reading.bearing_deg) <= cone.half_angle_deg
    if not (ultra or infra):
        return events
    detector = (
        ZoneDetector.ambos
        if ultra and infra
        else ZoneDetector.ultrasonido
        if ultra
        else ZoneDetector.infrarrojo
    )
    tag = (reading.rfid_tag or "").strip().upper() or None
    authorized = tag is not None and tag in authorized_tags
    events.append(
        Classified(
            ZoneEventKind.acceso_autorizado if authorized else ZoneEventKind.intrusion,
            detector,
            reading.ultrasonic_m if ultra else None,
            authorized,
        )
    )
    return events


def cone_polygon(
    lat: float, lon: float, heading_deg: float, cone: Cone, steps: int = 12
) -> list[list[float]]:
    """Sector circular [lon, lat] para dibujar el cono en el mapa (aprox. plana, < 100 m)."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    ring = [[lon, lat]]
    for i in range(steps + 1):
        ang = math.radians(heading_deg - cone.half_angle_deg + 2 * cone.half_angle_deg * i / steps)
        ring.append(
            [
                lon + cone.range_m * math.sin(ang) / m_per_deg_lon,
                lat + cone.range_m * math.cos(ang) / m_per_deg_lat,
            ]
        )
    ring.append([lon, lat])
    return ring
