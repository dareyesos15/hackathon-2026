"""Estado de ejecución compartido: gazetteer en memoria y proveedor de similitud."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.geo import Gazetteer, PlaceEntry
from app.core.similarity import SimilarityProvider, build_provider
from app.models import Place


@dataclass
class RuntimeState:
    gazetteer: Gazetteer
    similarity: SimilarityProvider


_state: RuntimeState | None = None


async def load_state(session: AsyncSession) -> RuntimeState:
    global _state
    rows = (
        await session.execute(
            select(
                Place.name,
                Place.kind,
                func.ST_Y(Place.geom),
                func.ST_X(Place.geom),
                Place.barrio,
                Place.aliases,
            )
        )
    ).all()
    entries = [
        PlaceEntry(name, kind, lat, lon, barrio, tuple(aliases))
        for name, kind, lat, lon, barrio, aliases in rows
    ]
    _state = RuntimeState(
        gazetteer=Gazetteer(entries),
        similarity=build_provider(get_settings().similarity_provider),
    )
    return _state


def get_state() -> RuntimeState:
    if _state is None:
        raise RuntimeError("El estado de la API no se ha cargado (lifespan)")
    return _state
