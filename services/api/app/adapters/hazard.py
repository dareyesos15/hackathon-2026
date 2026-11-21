"""Proveedor de amenaza (PGA/daño por manzana). P0: neutro; P1 conecta acelerógrafos tipo RAMAN.

Interfaz `HazardProvider` (principio VI): el ShakeMap/FDSN del SGC será otra implementación.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PhysicalConsistency:
    """Valor 0–1 de qué tan consistente es lo reportado con la amenaza estimada."""

    value: float
    detail: str
    has_data: bool


class HazardProvider(Protocol):
    def consistency(self, manzana_id: str | None, category: str) -> PhysicalConsistency: ...


class NeutralHazardProvider:
    """Sin sensores (P0): consistencia neutra, visible como "sin dato de sensor"."""

    def consistency(self, manzana_id: str | None, category: str) -> PhysicalConsistency:
        return PhysicalConsistency(value=0.5, detail="sin dato de sensor (neutro)", has_data=False)


hazard_provider: HazardProvider = NeutralHazardProvider()
