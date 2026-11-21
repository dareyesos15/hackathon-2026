"""Pendiente del terreno por manzana (research R11). Interfaz `TerrainProvider` (principio VI).

`SyntheticTerrain`: pendiente SIMULADA y determinista a partir de la zona sísmica de la manzana
(ladera 25–60°, meseta 3–15°) y un hash de su id. Un modelo digital de elevación de IDE-UNAL o
del IGAC sería otra implementación.
"""

from __future__ import annotations

import hashlib
from typing import Protocol


class TerrainProvider(Protocol):
    def slope_deg(self, manzana_id: str, seismic_zone: str) -> float: ...


class SyntheticTerrain:
    def slope_deg(self, manzana_id: str, seismic_zone: str) -> float:
        h = int(hashlib.sha256(manzana_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if "ladera" in seismic_zone.lower():
            return round(25.0 + 35.0 * h, 1)
        return round(3.0 + 12.0 * h, 1)


terrain_provider: TerrainProvider = SyntheticTerrain()
