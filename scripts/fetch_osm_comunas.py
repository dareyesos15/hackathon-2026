"""Descarga los límites reales de las 12 comunas de Manizales desde OpenStreetMap.

Se ejecuta UNA vez con internet; el resultado queda versionado en data/geo/comunas.geojson
para que la demo funcione sin red (offline-first). generate_geo.py lo usa para recortar el
casco urbano y asignar la comuna de cada barrio.

Datos © colaboradores de OpenStreetMap, licencia ODbL (https://www.openstreetmap.org/copyright).
Uso:
    python scripts/fetch_osm_comunas.py [--out data/geo/comunas.geojson]
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import LineString, mapping
from shapely.ops import polygonize, unary_union

OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:90][bbox:5.015,-75.56,5.105,-75.44];
relation["boundary"="administrative"]["admin_level"="8"]["name"~"^Comuna"];
out geom;
"""


def fetch() -> dict:
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "dacora-prototype"})
    with urllib.request.urlopen(req, timeout=120) as res:  # noqa: S310 (URL fija)
        return json.load(res)


def to_feature(rel: dict) -> dict:
    lines = [
        LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        for m in rel["members"]
        if m["type"] == "way" and m.get("role", "outer") in ("outer", "") and "geometry" in m
    ]
    shape = unary_union(list(polygonize(unary_union(lines))))
    name = rel["tags"]["name"].removeprefix("Comuna ").strip()
    return dict(
        type="Feature",
        geometry=mapping(shape.simplify(0.00005)),
        properties=dict(name=name, osm_id=rel["id"], source="OpenStreetMap (ODbL)"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data/geo/comunas.geojson",
    )
    args = parser.parse_args()
    features = sorted(
        (to_feature(e) for e in fetch()["elements"]), key=lambda f: f["properties"]["name"]
    )
    out = dict(
        type="FeatureCollection",
        name="comunas",
        attribution="© OpenStreetMap contributors, ODbL",
        features=features,
    )
    args.out.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(features)} comunas → {args.out}")


if __name__ == "__main__":
    main()
