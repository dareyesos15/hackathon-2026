"""Genera la geografía SIMULADA de Manizales para la demo (research R7).

Salidas (versionadas en data/geo/):
- gazetteer.csv: barrios, vías y referencias con centroides APROXIMADOS y alias normalizados.
- barrios.geojson: polígonos de Voronoi de los barrios recortados al casco urbano aproximado.
- manzanas.geojson: grilla regular (~200 m) dentro del casco, con atributos sintéticos.

Todo lleva source = "SIMULADO". Reemplazar por datos del geoportal municipal o del DANE es
cambiar estos archivos (plan 30–90 días). Uso:
    python scripts/generate_geo.py [--out data/geo]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import unicodedata
from pathlib import Path

from shapely.geometry import MultiPoint, Point, box, mapping
from shapely.ops import unary_union, voronoi_diagram

SEED = 20260810
SOURCE = "SIMULADO"
CELL_DEG = 0.0018  # ~200 m

# (nombre, tipo, lat, lon, comuna, alias extra). Coordenadas aproximadas, solo para la demo.
BARRIOS: list[tuple[str, float, float, str, list[str]]] = [
    ("Centro", 5.0689, -75.5174, "Cumanday", ["el centro", "centro historico"]),
    ("Chipre", 5.0705, -75.5285, "Atardeceres", []),
    ("Villa Pilar", 5.0612, -75.5212, "Atardeceres", ["villapilar"]),
    ("Arenillo", 5.0560, -75.5262, "Atardeceres", []),
    ("San José", 5.0722, -75.5098, "San José", ["san jose"]),
    ("Los Agustinos", 5.0703, -75.5128, "Cumanday", ["agustinos"]),
    ("Marmato", 5.0742, -75.5142, "San José", []),
    ("Galán", 5.0748, -75.5205, "Cumanday", ["galan"]),
    ("Solferino", 5.0762, -75.5088, "San José", []),
    ("Campohermoso", 5.0732, -75.5048, "San José", ["campo hermoso"]),
    ("Fundadores", 5.0652, -75.5052, "Cumanday", []),
    ("Aranjuez", 5.0628, -75.5072, "La Estación", []),
    ("Belén", 5.0641, -75.5002, "La Estación", ["belen"]),
    ("Laureles", 5.0612, -75.4982, "Palogrande", []),
    ("El Cable", 5.0590, -75.4958, "Palogrande", ["cable"]),
    ("Estrella", 5.0562, -75.4972, "Palogrande", ["la estrella"]),
    ("Palogrande", 5.0575, -75.4930, "Palogrande", []),
    ("Versalles", 5.0568, -75.4898, "Palogrande", []),
    ("Palermo", 5.0545, -75.4878, "Palogrande", []),
    ("Baja Suiza", 5.0540, -75.4908, "Ecoturístico Cerro de Oro", []),
    ("Alta Suiza", 5.0528, -75.4868, "Ecoturístico Cerro de Oro", []),
    ("Milán", 5.0505, -75.4825, "Ecoturístico Cerro de Oro", ["milan"]),
    ("Sancancio", 5.0482, -75.4958, "Ecoturístico Cerro de Oro", []),
    ("La Florida", 5.0468, -75.4788, "Ecoturístico Cerro de Oro", ["florida"]),
    ("La Sultana", 5.0422, -75.4878, "Tesorito", ["sultana"]),
    ("La Francia", 5.0485, -75.4918, "Universitaria", ["francia"]),
    ("La Enea", 5.0302, -75.4652, "La Fuente", ["enea"]),
    ("Bosques del Norte", 5.0898, -75.4952, "Ciudadela del Norte", ["bosques"]),
    ("La Linda", 5.0818, -75.5248, "Atardeceres", []),
    ("El Carmen", 5.0782, -75.5152, "San José", ["carmen"]),
]

# Vías y referencias: (nombre, tipo, lat, lon, barrio, alias)
REFERENCIAS: list[tuple[str, str, float, float, str, list[str]]] = [
    (
        "Avenida Santander",
        "via",
        5.0612,
        -75.5002,
        "Laureles",
        ["av santander", "avenida santander", "santander", "av. santander"],
    ),
    (
        "Avenida Paralela",
        "via",
        5.0578,
        -75.4992,
        "Estrella",
        ["av paralela", "paralela", "avenida paralela"],
    ),
    (
        "Carrera 23",
        "via",
        5.0668,
        -75.5142,
        "Centro",
        ["cra 23", "carrera 23", "kra 23", "cr 23", "la 23", "cra23"],
    ),
    (
        "Catedral",
        "referencia",
        5.0687,
        -75.5173,
        "Centro",
        ["catedral basilica", "la catedral", "plaza de bolivar"],
    ),
    ("Coliseo Mayor", "referencia", 5.0612, -75.5048, "Aranjuez", ["coliseo"]),
    (
        "Hospital Santa Sofía",
        "referencia",
        5.0638,
        -75.4992,
        "Belén",
        ["santa sofia", "hospital santa sofia"],
    ),
    (
        "Torre del Cable Aéreo",
        "referencia",
        5.0597,
        -75.4966,
        "El Cable",
        ["cable aereo", "torre del cable"],
    ),
    ("Estadio Palogrande", "referencia", 5.0560, -75.4920, "Palogrande", ["estadio"]),
    (
        "Monumento a los Colonizadores",
        "referencia",
        5.0723,
        -75.5302,
        "Chipre",
        ["monumento", "colonizadores"],
    ),
    ("Plaza de Mercado", "referencia", 5.0722, -75.5212, "Galán", ["galerias", "la galeria"]),
]


def normalize(text: str) -> str:
    """Minúsculas, sin tildes, sin signos; igual que app/core/geo.py."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def build_gazetteer() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, lat, lon, comuna, extra in BARRIOS:
        aliases = sorted({normalize(name), *(normalize(a) for a in extra)})
        rows.append(
            dict(
                name=name,
                kind="barrio",
                lat=f"{lat:.5f}",
                lon=f"{lon:.5f}",
                barrio=name,
                comuna=comuna,
                aliases="|".join(aliases),
                source=SOURCE,
            )
        )
    comunas = {b[3]: b for b in BARRIOS}
    for comuna, (_, lat, lon, _, _) in comunas.items():
        rows.append(
            dict(
                name=f"Comuna {comuna}",
                kind="comuna",
                lat=f"{lat:.5f}",
                lon=f"{lon:.5f}",
                barrio=next(b[0] for b in BARRIOS if b[3] == comuna),
                comuna=comuna,
                aliases="|".join(sorted({normalize(f"comuna {comuna}")})),
                source=SOURCE,
            )
        )
    barrio_comuna = {b[0]: b[3] for b in BARRIOS}
    for name, kind, lat, lon, barrio, extra in REFERENCIAS:
        aliases = sorted({normalize(name), *(normalize(a) for a in extra)})
        rows.append(
            dict(
                name=name,
                kind=kind,
                lat=f"{lat:.5f}",
                lon=f"{lon:.5f}",
                barrio=barrio,
                comuna=barrio_comuna[barrio],
                aliases="|".join(aliases),
                source=SOURCE,
            )
        )
    return rows


def build_polygons() -> tuple[dict, dict]:
    rng = random.Random(SEED)
    points = [Point(lon, lat) for _, lat, lon, _, _ in BARRIOS]
    # Casco urbano aproximado: unión de círculos de ~700 m alrededor de cada barrio.
    urban = unary_union([p.buffer(0.0065) for p in points]).simplify(0.0003)
    cells = voronoi_diagram(MultiPoint(points), envelope=urban.envelope.buffer(0.01))

    barrio_features = []
    barrio_shapes: list[tuple[str, str, object]] = []
    for cell in cells.geoms:
        idx = next(i for i, p in enumerate(points) if cell.contains(p))
        name, _, _, comuna, _ = BARRIOS[idx]
        shape = cell.intersection(urban)
        barrio_shapes.append((name, comuna, shape))
        barrio_features.append(
            dict(
                type="Feature",
                geometry=mapping(shape),
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
                barrio, comuna = next(
                    ((b, c) for b, c, s in barrio_shapes if s.contains(center)),
                    (barrio_shapes[0][0], barrio_shapes[0][1]),
                )
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

    rows = build_gazetteer()
    with (args.out / "gazetteer.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    barrios, manzanas = build_polygons()
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
