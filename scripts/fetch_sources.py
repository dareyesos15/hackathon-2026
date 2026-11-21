"""Descarga las fuentes públicas reales del tablero de recuperación y guarda su copia fechada.

Cada fuente queda en data/sources/<nombre>.json con la URL consultada, la fecha, la licencia y la
huella SHA-256 de los registros (respaldo verificable; la API lee esas copias sin internet).
Si una fuente falla, se conserva la copia anterior y se informa.

Uso (desde la raíz del repo, con internet):
    uv run --project services/api python scripts/fetch_sources.py
    uv run --project services/api python scripts/fetch_sources.py --only secop
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

import httpx  # noqa: E402

from app.adapters.public_sources import (  # noqa: E402
    Snapshot,
    fetch_cdiac,
    fetch_secop,
    fetch_usgs,
)
from app.config import get_settings  # noqa: E402

OUT = ROOT / "data" / "sources"


def _save(snap: Snapshot) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{snap.name}.json"
    path.write_text(json.dumps(snap.to_json(), ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"  ok  {snap.name}: {len(snap.records)} registros · sha256 {snap.sha256[:12]}…")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["usgs", "secop", "cdiac"], action="append")
    args = parser.parse_args()
    wanted = set(args.only or ["usgs", "secop", "cdiac"])
    now = datetime.now(UTC).replace(microsecond=0)
    failures = 0
    headers = {"User-Agent": "dacora-hackathon/0.1 (datos abiertos)"}
    with httpx.Client(timeout=60.0, headers=headers, follow_redirects=True) as client:
        for name, fetch in (("usgs", fetch_usgs), ("secop", fetch_secop)):
            if name not in wanted:
                continue
            try:
                _save(fetch(client, now))
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                failures += 1
                print(f"  ERR {name}: {exc} (se conserva la copia anterior)")
    if "cdiac" in wanted:
        s = get_settings()
        catalog = ROOT / "data" / "geo" / "cdiac_rain_stations.json"
        try:
            _save(asyncio.run(fetch_cdiac(s.cdiac_base_url, catalog, now)))
        except Exception as exc:  # noqa: BLE001 - se informa y se conserva la copia anterior
            failures += 1
            print(f"  ERR cdiac: {exc} (se conserva la copia anterior)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
