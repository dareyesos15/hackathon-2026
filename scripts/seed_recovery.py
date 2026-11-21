"""Siembra datos SIMULADOS del módulo de recuperación (specs/003) a través de la API REST.

Deja la pantalla /recuperacion con cifras para la demo: predios inspeccionados con semáforo
(incluidas visitas repetidas al mismo predio escrito de otra forma), hogares del censo único,
ayudas entregadas (una repetida con justificación) y ocupación de albergues.

Los documentos son códigos sintéticos `SIM…`: nunca cédulas reales (Ley 1581 de 2012). La API
solo guarda su HMAC.

Uso (con la API arriba):
    python scripts/seed_recovery.py
`replay_scenario.py` lo llama solo después de `--reset`.
"""

from __future__ import annotations

import sys

import httpx
from _client import api_client

# Casos preparados para mostrar EN VIVO en la demo (ver docs/guion_demo.md).
DEMO_EXISTING_DOCUMENT = "SIM100001"  # ya está en el censo → la API lo reconoce
DEMO_AID_DOCUMENT = "SIM100002"  # ya recibió mercado → la segunda entrega se bloquea

BARRIOS = ["Centro", "Milán", "Palogrande", "Chipre", "La Enea", "San José", "Villa Pilar"]

# (barrio, dirección, color, daño). Dirección escrita como la anotaría un inspector.
INSPECTIONS = [
    ("Centro", "Cra. 23 # 24-15", "rojo", "colapso"),
    ("Centro", "Cra. 22 # 25-40", "rojo", "mayor"),
    ("Centro", "Calle 26 # 21-08", "amarillo", "mediano_uso_restringido"),
    ("Centro", "Cra. 21 # 23-31", "amarillo", "mediano_uso_restringido"),
    ("Centro", "Calle 24 # 22-50", "verde", "menor"),
    ("Milán", "Calle 65 # 23B-12", "rojo", "mayor"),
    ("Milán", "Cra. 23C # 64-20", "rojo", "mayor"),
    ("Milán", "Calle 66 # 23-45", "amarillo", "mediano_uso_restringido"),
    ("Milán", "Cra. 24 # 65-10", "verde", "menor"),
    ("Milán", "Calle 64A # 23-70", "verde", "menor"),
    ("Palogrande", "Cra. 27 # 62-15", "amarillo", "menor"),
    ("Palogrande", "Calle 62 # 26-30", "verde", "menor"),
    ("Palogrande", "Cra. 26 # 61-05", "rojo", "mediano_uso_restringido"),
    ("Chipre", "Av. 12 de Octubre # 9-40", "amarillo", "mediano_uso_restringido"),
    ("Chipre", "Calle 10 # 12-22", "verde", "menor"),
    ("Chipre", "Cra. 12 # 9-15", "rojo", "colapso"),
    ("La Enea", "Calle 98 # 35-10", "verde", "menor"),
    ("La Enea", "Cra. 35 # 97-60", "amarillo", "mediano_uso_restringido"),
    ("San José", "Calle 19 # 15-30", "rojo", "mayor"),
    ("San José", "Cra. 15 # 18-12", "amarillo", "mediano_uso_restringido"),
    ("Villa Pilar", "Calle 48 # 12-05", "verde", "menor"),
    ("Villa Pilar", "Cra. 12 # 47-33", "amarillo", "mediano_uso_restringido"),
]

# Segunda visita al mismo predio escrito distinto: la API lo reconoce como el mismo predio.
REVISITS = [
    ("Centro", "carrera 23 24 15", "rojo", "colapso"),
    ("Milán", "CL 65 No. 23B - 12", "rojo", "mayor"),
    ("Palogrande", "KR 27 # 62 - 15", "verde", "menor"),
]

# (documento sintético, barrio, dirección, miembros, mascotas, RUD, vulnerabilidad)
HOUSEHOLDS = [
    ("SIM100001", "Centro", "Cra. 23 # 24-15", 4, 1, "inscrito", {"children": True}),
    ("SIM100002", "Centro", "Cra. 22 # 25-40", 3, 0, "inscrito", {"elderly": True}),
    ("SIM100003", "Centro", "Calle 26 # 21-08", 5, 2, "pendiente", {"children": True}),
    ("SIM100004", "Milán", "Calle 65 # 23B-12", 2, 0, "inscrito", {"elderly": True}),
    ("SIM100005", "Milán", "Cra. 23C # 64-20", 6, 1, "inscrito", {"disability": True}),
    ("SIM100006", "Milán", "Calle 66 # 23-45", 3, 0, "pendiente", {}),
    ("SIM100007", "Palogrande", "Cra. 26 # 61-05", 4, 0, "inscrito", {"pregnancy": True}),
    ("SIM100008", "Chipre", "Cra. 12 # 9-15", 5, 3, "inscrito", {"children": True}),
    ("SIM100009", "Chipre", "Av. 12 de Octubre # 9-40", 2, 0, "pendiente", {"elderly": True}),
    ("SIM100010", "San José", "Calle 19 # 15-30", 7, 1, "inscrito", {"children": True}),
    ("SIM100011", "San José", "Cra. 15 # 18-12", 3, 0, "pendiente", {}),
    ("SIM100012", "La Enea", "Cra. 35 # 97-60", 4, 2, "inscrito", {"disability": True}),
    ("SIM100013", "Villa Pilar", "Cra. 12 # 47-33", 2, 0, "pendiente", {"elderly": True}),
    ("SIM100014", "Centro", "Cra. 21 # 23-31", 3, 1, "inscrito", {}),
]

# (documento, tipo de ayuda). Todos reciben mercado; los hogares con predio rojo, kit y arriendo.
AID = (
    [(doc, "mercado") for doc, *_ in HOUSEHOLDS]
    + [(doc, "kit") for doc in ("SIM100001", "SIM100002", "SIM100004", "SIM100005", "SIM100008")]
    + [(doc, "subsidio_arriendo") for doc in ("SIM100001", "SIM100005", "SIM100008", "SIM100010")]
    + [(doc, "albergue") for doc in ("SIM100008", "SIM100010")]
)
REPEATED_AID = ("SIM100005", "mercado", "Hogar de 6 personas con persona con discapacidad")

# Ocupación de albergues por código (personas, mascotas).
SHELTERS = {"ALB-01": (212, 18), "ALB-02": (96, 7), "ALB-03": (64, 3), "ALB-04": (31, 4)}


def _manzanas_by_barrio(client: httpx.Client) -> dict[str, str]:
    """Primera manzana de cada barrio de la demo, leída de la API (no se inventan códigos)."""
    resp = client.get("/recovery/manzanas")
    resp.raise_for_status()
    first: dict[str, str] = {}
    for row in resp.json():
        first.setdefault(row["barrio"], row["id"])
    missing = [b for b in BARRIOS if b not in first]
    if missing:
        raise SystemExit(f"Barrios sin manzanas en la geografía: {', '.join(missing)}")
    return first


def _post(client: httpx.Client, path: str, body: dict, ok: tuple[int, ...] = (200, 201)) -> dict:
    resp = client.post(path, json=body)
    if resp.status_code not in ok:
        print(f"  {path} → {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json()


def seed(client: httpx.Client) -> dict[str, int]:
    manzanas = _manzanas_by_barrio(client)
    counts = {"inspecciones": 0, "hogares": 0, "ayudas": 0, "albergues": 0}

    for barrio, address, color, damage in INSPECTIONS + REVISITS:
        _post(
            client,
            "/recovery/inspections",
            {
                "manzana_id": manzanas[barrio],
                "address": address,
                "color": color,
                "damage_level": damage,
                "notes": "Inspección SIMULADA",
            },
        )
        counts["inspecciones"] += 1

    for doc, barrio, address, members, pets, rud, vulnerability in HOUSEHOLDS:
        data = _post(
            client,
            "/recovery/households",
            {
                "document": doc,
                "manzana_id": manzanas[barrio],
                "address": address,
                "members_count": members,
                "pets_count": pets,
                "rud_status": rud,
                "vulnerability": vulnerability,
            },
        )
        counts["hogares"] += int(data["created"])

    for doc, aid_type in AID:
        # 409 = ya entregada (p. ej. si se corre dos veces sin reiniciar): no es error.
        resp = client.post("/recovery/aid", json={"document": doc, "aid_type": aid_type})
        if resp.status_code == 201:
            counts["ayudas"] += 1
        elif resp.status_code != 409:
            resp.raise_for_status()
    doc, aid_type, why = REPEATED_AID
    resp = client.post(
        "/recovery/aid", json={"document": doc, "aid_type": aid_type, "justification": why}
    )
    counts["ayudas"] += int(resp.status_code == 201)

    shelters = client.get("/recovery/shelters")
    shelters.raise_for_status()
    for shelter in shelters.json()["items"]:
        if shelter["code"] in SHELTERS:
            people, pets = SHELTERS[shelter["code"]]
            resp = client.patch(
                f"/recovery/shelters/{shelter['id']}", json={"people": people, "pets": pets}
            )
            resp.raise_for_status()
            counts["albergues"] += 1
    return counts


def main() -> int:
    with api_client() as client:
        counts = seed(client)
    print(
        "Recuperación SIMULADA: "
        + ", ".join(f"{v} {k}" for k, v in counts.items())
        + f". Casos en vivo: hogar ya censado {DEMO_EXISTING_DOCUMENT}, "
        f"mercado ya entregado a {DEMO_AID_DOCUMENT}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
