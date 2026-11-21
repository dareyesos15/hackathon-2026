"""Reglas puras del tablero de recuperación unificado (índice, etapas, situación de hogares).

Sin acceso a la base de datos: el router reúne los datos y estas funciones deciden. Las
fuentes externas (servicios, economía, finanzas, réplicas) llegan SIMULADAS desde
data/seed/recovery_context.json; en producción las reemplaza un adaptador por fuente.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.config import get_settings

StageStatus = Literal["pendiente", "verde", "amarillo", "rojo"]
Situation = Literal["albergue", "arriendo", "casa", "sin_solucion"]

SERVICES = ("agua", "energia", "gas", "telecom", "vias")
#: Pesos del índice de recuperación: habitabilidad (3), servicios (6), familias (7), economía (9).
INDEX_WEIGHTS = {"habitabilidad": 0.25, "servicios": 0.25, "familias": 0.25, "economia": 0.25}


@lru_cache
def load_context(path: Path | None = None) -> dict[str, Any]:
    target = path or get_settings().data_dir / "seed" / "recovery_context.json"
    data: dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
    return data


def pct(part: float, total: float) -> float | None:
    return round(100.0 * part / total, 1) if total else None


def habitability_score(verde: int, amarillo: int, rojo: int) -> float | None:
    """% de predios evaluados habitables; uso restringido cuenta la mitad."""
    return pct(verde + 0.5 * amarillo, verde + amarillo + rojo)


def services_score(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    return round(sum(float(row[s]) for s in SERVICES) / len(SERVICES), 1)


def recovery_index(components: dict[str, float | None]) -> float | None:
    """Promedio ponderado de los componentes disponibles (los que no tienen datos no cuentan)."""
    available = {k: v for k, v in components.items() if v is not None and k in INDEX_WEIGHTS}
    if not available:
        return None
    weight = sum(INDEX_WEIGHTS[k] for k in available)
    return round(sum(INDEX_WEIGHTS[k] * v for k, v in available.items()) / weight, 1)


def household_situation(housing_aid: str | None, property_color: str | None) -> Situation:
    """Dónde vive hoy la familia según su última ayuda de vivienda y el semáforo de su predio."""
    if housing_aid == "albergue":
        return "albergue"
    if housing_aid == "subsidio_arriendo":
        return "arriendo"
    if property_color == "rojo":
        return "sin_solucion"
    return "casa"


@dataclass(frozen=True)
class StageWindow:
    number: int
    title: str
    question: str
    start_day: int
    end_day: int


STAGES = (
    StageWindow(1, "El golpe", "¿Cuánto perdimos?", 0, 7),
    StageWindow(2, "La plata disponible", "¿Con qué contamos?", 3, 15),
    StageWindow(3, "La plata en movimiento", "¿Le está llegando a la gente?", 7, 45),
    StageWindow(4, "La reactivación", "¿Volvió a moverse el comercio?", 15, 60),
    StageWindow(5, "La estabilización", "¿Estamos como antes?", 45, 90),
)


def stage_status(day: int, stage: StageWindow, progress: float | None) -> StageStatus:
    """Verde a tiempo, amarillo con retraso, rojo estancada; pendiente si aún no empieza.

    El avance esperado crece lineal dentro de la ventana de la etapa y es 100 % al cerrarla.
    """
    if day < stage.start_day or progress is None:
        return "pendiente"
    span = max(stage.end_day - stage.start_day, 1)
    expected = min(1.0, max((day - stage.start_day) / span, 0.05))
    ratio = progress / expected
    if ratio >= 0.9:
        return "verde"
    if ratio >= 0.6:
        return "amarillo"
    return "rojo"
