"""Genera la geografía de Manizales para la demo (research R7).

Entradas:
- data/geo/comunas.geojson: límites REALES de las 12 comunas (OpenStreetMap, ODbL), descargados
  una vez con scripts/fetch_osm_comunas.py y versionados para trabajar sin red.
- Las listas BARRIOS y REFERENCIAS de este archivo: puntos REALES tomados de OpenStreetMap
  (nodos place=neighbourhood, vías y edificaciones; consulta del 21 nov 2026).

Salidas (versionadas en data/geo/):
- gazetteer.csv: barrios, comunas, vías y referencias con coordenadas de OSM y alias.
- barrios.geojson: polígonos de Voronoi de los barrios recortados a las comunas reales.
  Los límites de barrio siguen siendo una APROXIMACIÓN (OSM no tiene polígonos de barrio).
- manzanas.geojson: grilla regular (~200 m) dentro del casco, con atributos SIMULADOS.

La comuna de cada barrio se calcula con el polígono real; el barrio de cada referencia es el
barrio más cercano. Uso:
    python scripts/generate_geo.py [--out data/geo]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import unicodedata
from pathlib import Path

from shapely.geometry import MultiPoint, Point, box, mapping, shape
from shapely.ops import unary_union, voronoi_diagram

SEED = 20260810
SOURCE = "SIMULADO"  # atributos de manzana y límites de barrio
OSM = "OpenStreetMap (ODbL)"  # coordenadas de barrios y referencias, límites de comuna
CELL_DEG = 0.0018  # ~200 m
URBAN_RADIUS_DEG = 0.0075  # ~830 m alrededor de cada barrio, dentro de las comunas

# (nombre, lat, lon, alias extra). Coordenadas de OpenStreetMap (place=neighbourhood).
BARRIOS: list[tuple[str, float, float, list[str]]] = [
    ("Centro", 5.06769, -75.51833, ["el centro", "centro historico"]),
    ("Chipre", 5.07584, -75.52544, []),
    ("Villa Pilar", 5.08396, -75.52595, ["villapilar"]),
    ("San José", 5.07203, -75.51488, ["san jose"]),
    ("Los Agustinos", 5.06962, -75.52180, ["agustinos"]),
    ("Marmato", 5.06250, -75.51590, []),
    ("Galán", 5.07451, -75.51184, ["galan"]),
    ("Solferino", 5.07643, -75.48759, []),
    ("Campohermoso", 5.07436, -75.52167, ["campo hermoso"]),
    ("Fundadores", 5.06633, -75.50988, []),
    ("Cervantes", 5.06341, -75.50948, []),
    ("Lleras", 5.06402, -75.50154, []),
    ("Aranjuez", 5.04254, -75.49978, []),
    ("Belén", 5.06116, -75.49258, ["belen"]),
    ("Versalles", 5.06315, -75.49881, []),
    ("Laureles", 5.05647, -75.48367, []),
    ("El Cable", 5.05634, -75.48642, ["cable"]),
    ("La Estrella", 5.05944, -75.48941, ["estrella"]),
    ("Palogrande", 5.05761, -75.48887, []),
    ("Palermo", 5.05144, -75.48864, []),
    ("Baja Suiza", 5.05536, -75.47960, []),
    ("Alta Suiza", 5.05110, -75.48151, []),
    ("Milán", 5.04590, -75.47986, ["milan"]),
    ("Sancancio", 5.04773, -75.49228, []),
    ("Fátima", 5.05255, -75.49648, ["fatima"]),
    ("Persia", 5.05833, -75.50299, []),
    ("La Florida", 5.03385, -75.48500, ["florida"]),
    ("La Sultana", 5.06108, -75.47277, ["sultana"]),
    ("La Francia", 5.06829, -75.53268, ["francia"]),
    ("Asturias", 5.05957, -75.52842, []),
    ("El Carmen", 5.06014, -75.51913, ["carmen"]),
    ("La Enea", 5.03182, -75.46306, ["enea"]),
    ("Sinaí", 5.07246, -75.48735, ["sinai"]),
    ("Bengala", 5.07839, -75.49059, []),
    ("Bosques del Norte", 5.08299, -75.48930, ["bosques"]),
]

# Vías y referencias: (nombre, tipo, lat, lon, alias). Coordenadas de OpenStreetMap.
# Para las vías, el punto es un tramo representativo (donde se concentran los reportes).
REFERENCIAS: list[tuple[str, str, float, float, list[str]]] = [
    (
        "Avenida Santander",
        "via",
        5.06216,
        -75.49415,
        ["av santander", "avenida santander", "santander", "av. santander"],
    ),
    (
        "Avenida Paralela",
        "via",
        5.06062,
        -75.49559,
        ["av paralela", "paralela", "avenida paralela"],
    ),
    (
        "Carrera 23",
        "via",
        5.06716,
        -75.51535,
        ["cra 23", "carrera 23", "kra 23", "cr 23", "la 23", "cra23"],
    ),
    (
        "Catedral",
        "referencia",
        5.06738,
        -75.51732,
        ["catedral basilica", "la catedral", "plaza de bolivar"],
    ),
    ("Coliseo Mayor", "referencia", 5.05804, -75.48845, ["coliseo"]),
    (
        "Hospital Santa Sofía",
        "referencia",
        5.05799,
        -75.52958,
        ["santa sofia", "hospital santa sofia"],
    ),
    (
        "Torre del Cable Aéreo",
        "referencia",
        5.05584,
        -75.48613,
        ["cable aereo", "torre del cable"],
    ),
    ("Estadio Palogrande", "referencia", 5.05703, -75.49009, ["estadio"]),
    (
        "Monumento a los Colonizadores",
        "referencia",
        5.07699,
        -75.52781,
        ["monumento", "colonizadores"],
    ),
    ("Plaza de Mercado", "referencia", 5.07165, -75.51719, ["galerias", "la galeria"]),
]

COMUNAS_FILE = Path(__file__).resolve().parents[1] / "data/geo/comunas.geojson"


def load_comunas(path: Path = COMUNAS_FILE) -> list[tuple[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(f["properties"]["name"], shape(f["geometry"])) for f in data["features"]]


def comuna_of(comunas: list[tuple[str, object]], lat: float, lon: float) -> str:
    """Comuna real que contiene el punto (o la más cercana si cae justo en el borde)."""
    p = Point(lon, lat)
    return min(comunas, key=lambda c: c[1].distance(p))[0]


def nearest_barrio(lat: float, lon: float) -> str:
    return min(BARRIOS, key=lambda b: (b[1] - lat) ** 2 + (b[2] - lon) ** 2)[0]


def normalize(text: str) -> str:
    """Minúsculas, sin tildes, sin signos; igual que app/core/geo.py."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def build_gazetteer(comunas: list[tuple[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, lat, lon, extra in BARRIOS:
        aliases = sorted({normalize(name), *(normalize(a) for a in extra)})
        rows.append(
            dict(
                name=name,
                kind="barrio",
                lat=f"{lat:.5f}",
                lon=f"{lon:.5f}",
                barrio=name,
                comuna=comuna_of(comunas, lat, lon),
                aliases="|".join(aliases),
                source=OSM,
            )
        )
    for comuna, geom in comunas:
        center = geom.representative_point()
        rows.append(
            dict(
                name=f"Comuna {comuna}",
                kind="comuna",
                lat=f"{center.y:.5f}",
                lon=f"{center.x:.5f}",
                barrio=nearest_barrio(center.y, center.x),
                comuna=comuna,
                aliases="|".join(sorted({normalize(f"comuna {comuna}")})),
                source=OSM,
            )
        )
    for name, kind, lat, lon, extra in REFERENCIAS:
        aliases = sorted({normalize(name), *(normalize(a) for a in extra)})
        rows.append(
            dict(
                name=name,
                kind=kind,
                lat=f"{lat:.5f}",
                lon=f"{lon:.5f}",
                barrio=nearest_barrio(lat, lon),
                comuna=comuna_of(comunas, lat, lon),
                aliases="|".join(aliases),
                source=OSM,
            )
        )
    return rows


def build_polygons(comunas: list[tuple[str, object]]) -> tuple[dict, dict]:
    rng = random.Random(SEED)
    points = [Point(lon, lat) for _, lat, lon, _ in BARRIOS]
    # Casco urbano: comunas reales, limitado a ~830 m de algún barrio (sin zonas rurales).
    near = unary_union([p.buffer(URBAN_RADIUS_DEG) for p in points])
    urban = unary_union([g for _, g in comunas]).intersection(near).simplify(0.0002)
    cells = voronoi_diagram(MultiPoint(points), envelope=urban.envelope.buffer(0.01))

    barrio_features = []
    barrio_shapes: list[tuple[str, str, object]] = []
    for cell in cells.geoms:
        idx = next(i for i, p in enumerate(points) if cell.contains(p))
        name, lat, lon, _ = BARRIOS[idx]
        comuna = comuna_of(comunas, lat, lon)
        cell_shape = cell.intersection(urban)
        barrio_shapes.append((name, comuna, cell_shape))
        barrio_features.append(
            dict(
                type="Feature",
                geometry=mapping(cell_shape),
                properties=dict(name=name, comuna=comuna, source=SOURCE),
            )
        )

    minx, miny, maxx, maxy = urban.bounds
    manzana_features = []
    n = 0
    y = miny
    while y < maxy:
        x = minx
        while x < maxx:
            cell = box(x, y, x + CELL_DEG, y + CELL_DEG)
            center = cell.centroid
            if urban.contains(center):
                barrio = next(
                    (b for b, _, bs in barrio_shapes if bs.contains(center)),
                    nearest_barrio(center.y, center.x),
                )
                comuna = comuna_of(comunas, center.y, center.x)
                n += 1
                old_core = barrio in {"Centro", "San José", "Los Agustinos", "Galán", "Marmato"}
                manzana_features.append(
                    dict(
                        type="Feature",
                        geometry=mapping(cell),
                        properties=dict(
                            id=f"MZ-{n:04d}",
                            barrio=barrio,
                            comuna=comuna,
                            seismic_zone="Zona 1 (meseta)" if x < -75.505 else "Zona 2 (ladera)",
                            population=rng.randint(60, 420),
                            buildings_pre_1984_pct=round(
                                rng.uniform(0.45, 0.85) if old_core else rng.uniform(0.05, 0.4), 2
                            ),
                            source=SOURCE,
                        ),
                    )
                )
            x += CELL_DEG
        y += CELL_DEG

    return (
        dict(type="FeatureCollection", name="barrios", features=barrio_features),
        dict(type="FeatureCollection", name="manzanas", features=manzana_features),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parents[1] / "data/geo"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    comunas = load_comunas()
    rows = build_gazetteer(comunas)
    with (args.out / "gazetteer.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    barrios, manzanas = build_polygons(comunas)
    for name, data in (("barrios", barrios), ("manzanas", manzanas)):
        (args.out / f"{name}.geojson").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    print(
        f"gazetteer: {len(rows)} lugares · barrios: {len(barrios['features'])} · "
        f"manzanas: {len(manzanas['features'])} → {args.out}"
    )


if __name__ == "__main__":
    main()
