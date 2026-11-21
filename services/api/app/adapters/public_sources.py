"""Fuentes públicas reales del tablero de recuperación, con copia fechada como respaldo.

Cada fuente se descarga con `scripts/fetch_sources.py` y se guarda en `data/sources/<nombre>.json`
con su procedencia: URL consultada, fecha y hora, licencia, atribución y huella SHA-256 de los
registros. La API solo lee esas copias (offline-first, principio VII): sin internet el tablero
sigue mostrando el último corte, con su fecha.

Fuentes:
- `usgs_sismos`: catálogo sísmico del USGS (servicio FDSN, dominio público) en 300 km alrededor
  de Manizales desde el 10 ago 2026. El servicio FDSN del SGC no respondió en las rutas
  públicas probadas; queda como siguiente fuente (mismo formato FDSN).
- `secop_sismo_manizales`: contratos de SECOP II (datos.gov.co, CC BY-SA 4.0) firmados en
  Manizales desde el 10 ago 2026 cuyo objeto menciona el sismo, la calamidad pública, los
  damnificados o el alojamiento temporal. Habeas Data: no se guardan nombres ni documentos de
  contratistas o representantes (personas naturales), solo entidad, objeto, fechas y valores.
- `cdiac_lluvia`: lluvia de las últimas 3 h por estación urbana del CDIAC/SIMAC (UNAL Manizales).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

MANIZALES = (5.0689, -75.5174)
EVENT_START = "2026-08-10"

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
SECOP_URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
SECOP_PAGE = (
    "https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h"
)

#: Palabras que ligan un contrato con el sismo (sin tildes, mayúsculas). "Emergencia",
#: "reconstrucción" y "escombros" solas traen contratos rutinarios y no cuentan.
SECOP_KEYWORDS = re.compile(
    r"\bSISM|CALAMIDAD|DAMNIFICAD|TERREMOTO|ALOJAMIENTO TEMPORAL|ARRENDAMIENTO TEMPORAL"
)
SECOP_FIELDS = (
    "id_contrato",
    "referencia_del_contrato",
    "nombre_entidad",
    "fecha_de_firma",
    "estado_contrato",
    "modalidad_de_contratacion",
    "objeto_del_contrato",
    "valor_del_contrato",
    "valor_facturado",
    "valor_pagado",
    "valor_pendiente_de_pago",
    "urlproceso",
)
MONEY_FIELDS = ("valor_del_contrato", "valor_facturado", "valor_pagado", "valor_pendiente_de_pago")


@dataclass(frozen=True)
class Snapshot:
    name: str
    title: str
    source: str
    query_url: str
    license: str
    attribution: str
    fetched_at: datetime
    records: list[dict[str, Any]]
    sha256: str

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "source": self.source,
            "query_url": self.query_url,
            "license": self.license,
            "attribution": self.attribution,
            "fetched_at": self.fetched_at.isoformat(),
            "record_count": len(self.records),
            "sha256": self.sha256,
            "records": self.records,
        }


def digest(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.upper()).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain)


def is_earthquake_contract(objeto: str) -> bool:
    return bool(SECOP_KEYWORDS.search(_norm(objeto)))


def _money(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------- descarga (con red)


def fetch_usgs(client: httpx.Client, now: datetime) -> Snapshot:
    params: dict[str, str | float] = {
        "format": "geojson",
        "starttime": EVENT_START,
        "latitude": MANIZALES[0],
        "longitude": MANIZALES[1],
        "maxradiuskm": 300,
        "minmagnitude": 2.5,
        "orderby": "time",
    }
    resp = client.get(USGS_URL, params=params)
    resp.raise_for_status()
    records = [
        {
            "id": f["id"],
            "time": datetime.fromtimestamp(f["properties"]["time"] / 1000, UTC).isoformat(),
            "magnitude": f["properties"]["mag"],
            "place": f["properties"]["place"],
            "depth_km": round(f["geometry"]["coordinates"][2], 1),
            "lat": f["geometry"]["coordinates"][1],
            "lon": f["geometry"]["coordinates"][0],
            "url": f["properties"]["url"],
        }
        for f in resp.json()["features"]
    ]
    return Snapshot(
        name="usgs_sismos",
        title="Sismos M ≥ 2,5 a 300 km de Manizales desde el 10 ago 2026",
        source="USGS · servicio FDSN",
        query_url=str(resp.url),
        license="Dominio público (U.S. Geological Survey)",
        attribution="U.S. Geological Survey, Earthquake Hazards Program",
        fetched_at=now,
        records=records,
        sha256=digest(records),
    )


def fetch_secop(client: httpx.Client, now: datetime) -> Snapshot:
    where = f"fecha_de_firma >= '{EVENT_START}' AND ciudad = 'Manizales'"
    params = {"$where": where, "$limit": "50000", "$order": "fecha_de_firma"}
    resp = client.get(SECOP_URL, params=params)
    resp.raise_for_status()
    records = []
    for row in resp.json():
        if not is_earthquake_contract(str(row.get("objeto_del_contrato", ""))):
            continue
        kept = {k: row.get(k) for k in SECOP_FIELDS}
        url = kept.get("urlproceso")
        kept["urlproceso"] = url.get("url") if isinstance(url, dict) else url
        for k in (
            "valor_del_contrato",
            "valor_facturado",
            "valor_pagado",
            "valor_pendiente_de_pago",
        ):
            kept[k] = _money(kept[k])
        kept["objeto_del_contrato"] = re.sub(r"\s+", " ", str(kept["objeto_del_contrato"]))[:400]
        records.append(kept)
    records.sort(key=lambda r: str(r["id_contrato"]))
    return Snapshot(
        name="secop_sismo_manizales",
        title="Contratos de SECOP II en Manizales ligados al sismo (desde el 10 ago 2026)",
        source="SECOP II · datos.gov.co",
        query_url=str(resp.url),
        license="CC BY-SA 4.0",
        attribution="Agencia Nacional de Contratación Pública - Colombia Compra Eficiente",
        fetched_at=now,
        records=records,
        sha256=digest(records),
    )


async def fetch_cdiac(base_url: str, catalog: Path, now: datetime) -> Snapshot:
    from app.adapters.rain import ATTRIBUTION, CdiacRainClient

    client = CdiacRainClient(base_url, catalog, timeout_s=20.0)
    readings = await client.fetch(now, timedelta(hours=24))
    records = [
        {
            "station_code": r.station.code,
            "station": r.station.name,
            "mm_3h": r.mm_3h,
            "last_data_at": r.last_data_at.isoformat(),
        }
        for r in sorted(readings, key=lambda r: r.station.code)
    ]
    return Snapshot(
        name="cdiac_lluvia",
        title="Lluvia de las últimas 3 h por estación urbana de Manizales",
        source="CDIAC / SIMAC · UNAL Manizales",
        query_url=f"{base_url.rstrip('/')}/getLastDayDataByStation/{{id}}",
        license="Datos abiertos del CDIAC (citar la fuente)",
        attribution=ATTRIBUTION,
        fetched_at=now,
        records=records,
        sha256=digest(records),
    )


# ------------------------------------------------------------------- lectura (sin red)


@dataclass(frozen=True)
class LoadedSnapshot:
    name: str
    title: str
    source: str
    query_url: str
    license: str
    attribution: str
    fetched_at: datetime
    sha256: str
    records: list[dict[str, Any]]
    verified: bool  # la huella coincide con los registros


def sources_dir() -> Path:
    from app.config import get_settings

    return get_settings().data_dir / "sources"


@lru_cache(maxsize=16)
def _load(path: Path, mtime: float) -> LoadedSnapshot | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        records = list(raw["records"])
        return LoadedSnapshot(
            name=raw["name"],
            title=raw["title"],
            source=raw["source"],
            query_url=raw["query_url"],
            license=raw["license"],
            attribution=raw["attribution"],
            fetched_at=datetime.fromisoformat(raw["fetched_at"]),
            sha256=raw["sha256"],
            records=records,
            verified=digest(records) == raw["sha256"],
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_snapshot(name: str, directory: Path | None = None) -> LoadedSnapshot | None:
    """Última copia guardada de una fuente; `None` si no se ha descargado nunca."""
    path = (directory or sources_dir()) / f"{name}.json"
    if not path.exists():
        return None
    return _load(path, path.stat().st_mtime)
