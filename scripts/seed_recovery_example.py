"""Casos de ejemplo del módulo de recuperación: 6 predios que recorren el flujo completo.

Material de capacitación para la entidad que opere Dacora (UGR, Bomberos, Desarrollo Social,
Cruz Roja). Cada caso es una situación típica del sismo y pasa por las mismas reglas que un
registro hecho a mano, porque todo se carga **por la API REST** (nunca directo a la base):

  revisión a predio (formato GUE-RPD-FR-02) → semáforo NSR-10 → censo único (RUD)
  → actas de entrega (kit, subsidio de arriendo, cupo en albergue) → derivaciones a entidades
  → necesidades en el tablero.

Identificables y repetibles: formatos y actas con números reservados 990001–990099 y documentos
ficticios de capacitación (Ley 1581: la API solo guarda su huella HMAC). Si ya están cargados, el
script no duplica nada. La guía caso por caso está en docs/guia_recuperacion.md.

Uso:
    docker compose exec api python scripts/seed_recovery_example.py
    API_BASE_URL=http://localhost:8080/api/v1 uv run --project services/api python \\
        scripts/seed_recovery_example.py
"""

from __future__ import annotations

import os
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import httpx
from _client import API_BASE_URL, api_client

TOKEN_AGENCIA = os.environ.get("TOKEN_AGENCIA", "agencia-demo")
FIRST_FORM = "990001"
AID_LABEL = {
    "subsidio_arriendo": "subsidio de arriendo",
    "kit": "kit de aseo y cocina",
    "mercado": "kit alimentario (mercado)",
    "albergue": "cupo en albergue",
}
DAMAGE_LABEL = {
    "menor": "daño menor",
    "mediano_uso_restringido": "uso restringido",
    "mayor": "daño mayor",
    "colapso": "colapso",
}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@dataclass
class Case:
    """Un predio de ejemplo y lo que se hace con él, en orden."""

    number: int
    title: str
    barrio: str
    address: str
    review: dict[str, Any]
    census: dict[str, Any] | None = None
    aids: list[dict[str, Any]] = field(default_factory=list)
    referrals_done: list[str] = field(default_factory=list)
    lesson: str = ""


def _doc(n: int) -> str:
    """Documento ficticio de capacitación (nunca de una persona real)."""
    return f"11111{n:05d}"


CASES = [
    Case(
        1,
        "Edificio con grietas y evacuación: familia al albergue",
        "Milán",
        "Carrera 23 # 64-12 apto 302",
        review={
            "form_number": "990001",
            "reviewed_at": "2026-08-11T15:20:00-05:00",
            "respondent_document": _doc(1),
            "respondent_relation": "propietario",
            "residents": 5,
            "minors": 2,
            "elderly": 1,
            "pets": 1,
            "event_types": ["sismo"],
            "structural_causes": ["evento_natural"],
            "affectation": "parcial",
            "affected_areas_m2": {"vivienda": 48},
            "belongings_loss": "nevera y dos camas",
            "referrals": ["ugr", "chec"],
            "evacuation_recommended": True,
            "notified_signed": True,
        },
        aids=[
            {"aid_type": "albergue", "shelter": "first", "act_number": "990101"},
            {"aid_type": "mercado", "quantity": 1, "act_number": "990102"},
        ],
        referrals_done=["ugr"],
        lesson="Evacuación → semáforo rojo, hogar creado en el censo, cupo en albergue "
        "(la ocupación sube sola) y derivaciones; la UGR ya marcó su visita, la CHEC sigue "
        "pendiente.",
    ),
    Case(
        2,
        "Casa colapsada de arrendatarios: subsidio de arriendo",
        "Centro",
        "Calle 22 # 21-35",
        review={
            "form_number": "990002",
            "reviewed_at": "2026-08-11T17:05:00-05:00",
            "respondent_document": _doc(2),
            "respondent_relation": "arrendatario",
            "owner_document": _doc(92),
            "residents": 3,
            "event_types": ["sismo"],
            "structural_causes": ["evento_natural", "falta_mantenimiento"],
            "affectation": "total",
            "affected_areas_m2": {"vivienda": 72},
            "belongings_loss": "enseres de cocina y ropa",
            "referrals": ["obras_publicas", "inspeccion_policia"],
            "evacuation_recommended": True,
            "color": "rojo",
            "damage_level": "colapso",
            "notified_signed": True,
        },
        census={
            "census_form_number": "990201",
            "members_count": 3,
            "tenure": "arrendatario",
            "age_6_17": 1,
            "age_18_59": 2,
            "female_members": 2,
            "losses": ["enseres", "herramientas_trabajo"],
        },
        aids=[
            {
                "aid_type": "subsidio_arriendo",
                "amount_cop": 550000,
                "months": 3,
                "act_number": "990103",
            }
        ],
        lesson="Afectación total con colapso → vivienda destruida en el RUD; el censo se "
        "completa sobre el mismo hogar (no se duplica) y el subsidio de arriendo lleva valor y "
        "meses.",
    ),
    Case(
        3,
        "Casa con daño moderado: uso restringido, la familia se queda",
        "San José",
        "Carrera 16 # 25-40",
        review={
            "form_number": "990003",
            "reviewed_at": "2026-08-12T09:40:00-05:00",
            "respondent_document": _doc(3),
            "respondent_relation": "propietario",
            "residents": 4,
            "minors": 1,
            "event_types": ["sismo"],
            "structural_causes": ["evento_natural"],
            "affectation": "parcial",
            "affected_areas_m2": {"vivienda": 12},
            "referrals": ["aguas_de_manizales"],
            "evacuation_recommended": False,
            "notified_signed": True,
        },
        aids=[{"aid_type": "kit", "quantity": 1, "act_number": "990104"}],
        lesson="Afectación parcial sin evacuación → semáforo amarillo (uso restringido); el "
        "hogar sigue en su vivienda y se deriva a Aguas de Manizales por la tubería.",
    ),
    Case(
        4,
        "Predio sin daño: se descarta en terreno",
        "Palermo",
        "Calle 65 # 23B-10",
        review={
            "form_number": "990004",
            "reviewed_at": "2026-08-12T11:15:00-05:00",
            "residents": 2,
            "event_types": ["sismo"],
            "affectation": "ninguna",
            "evacuation_recommended": False,
            "notified_signed": True,
        },
        lesson="Sin afectación → semáforo verde. Sin documento del encuestado el hogar no entra "
        "al censo: queda la revisión y el predio cuenta como evaluado.",
    ),
    Case(
        5,
        "Familia vulnerable evacuada sin solución de vivienda",
        "Los Agustinos",
        "Carrera 19 # 18-22",
        review={
            "form_number": "990005",
            "reviewed_at": "2026-08-13T08:30:00-05:00",
            "respondent_document": _doc(5),
            "respondent_relation": "otro",
            "residents": 4,
            "elderly": 2,
            "disability": 1,
            "event_types": ["sismo", "deslizamiento"],
            "structural_causes": ["evento_natural"],
            "affectation": "total",
            "affected_areas_m2": {"vivienda": 60, "vial": 15},
            "referrals": ["corpocaldas", "ugr"],
            "evacuation_recommended": True,
            "notified_signed": False,
        },
        lesson="Evacuada y sin albergue ni arriendo todavía → aparece como necesidad crítica "
        "en el tablero (familia en predio rojo sin solución). El formato quedó sin firma del "
        "notificado.",
    ),
    Case(
        6,
        "Segunda visita al edificio del caso 1 y entrega repetida",
        "Milán",
        "Carrera 23 # 64-12 apto 302",
        review={
            "form_number": "990006",
            "reviewed_at": "2026-08-20T10:00:00-05:00",
            "respondent_document": _doc(1),
            "respondent_relation": "propietario",
            "residents": 5,
            "minors": 2,
            "elderly": 1,
            "event_types": ["sismo"],
            "structural_causes": ["evento_natural"],
            "affectation": "total",
            "affected_areas_m2": {"vivienda": 48},
            "evacuation_recommended": True,
            "notified_signed": True,
        },
        aids=[
            {
                "aid_type": "mercado",
                "quantity": 1,
                "act_number": "990105",
                "justification": "Hogar de 5 personas en albergue, el primer mercado no alcanzó",
            }
        ],
        lesson="La segunda revisión se une al mismo predio (visita n.º 2) y al mismo hogar; el "
        "segundo mercado dentro del periodo solo se entrega con justificación y queda marcado.",
    ),
]


def _manzanas(client: httpx.Client) -> dict[str, str]:
    by_barrio: dict[str, str] = {}
    for m in client.get("/recovery/manzanas").raise_for_status().json():
        by_barrio.setdefault(_norm(m["barrio"]), m["id"])
    return by_barrio


def _shelter(client: httpx.Client, members: int) -> dict[str, Any]:
    """Albergue abierto con más cupos libres para `members` personas."""
    items = client.get("/recovery/shelters").raise_for_status().json()["items"]
    open_ = [s for s in items if s.get("status", "abierto") == "abierto"]
    return max(open_, key=lambda s: s["capacity"] - s["people"]) if open_ else items[0]


def _already_loaded(client: httpx.Client) -> bool:
    reviews = client.get("/recovery/reviews").raise_for_status().json()
    return any(r.get("form_number") == FIRST_FORM for r in reviews)


def main() -> int:
    print(f"Casos de ejemplo de recuperación → {API_BASE_URL}")
    with api_client() as client:
        if _already_loaded(client):
            print("Los casos de ejemplo ya estaban cargados (formato N.º 990001). Nada que hacer.")
            return 0
        manzanas = _manzanas(client)
        used_shelter: dict[str, Any] | None = None
        for case in CASES:
            manzana = manzanas.get(_norm(case.barrio))
            if manzana is None:
                print(f"  ✗ caso {case.number}: no hay manzanas del barrio {case.barrio}")
                return 1
            print(f"\nCaso {case.number}. {case.title} ({case.barrio})")
            body = {"manzana_id": manzana, "address": case.address, **case.review}
            resp = client.post("/recovery/reviews", json=body)
            if resp.status_code != 201:
                print(f"  ✗ revisión: {resp.status_code} {resp.text}")
                return 1
            review = resp.json()
            print(
                f"  · Revisión N.º {review['form_number']}: semáforo {review['color']} "
                f"({DAMAGE_LABEL[review['damage_level']]}), visita n.º {review['visit_number']}"
            )
            for step in review["next_steps"]:
                print(f"    - {step}")

            document = case.review.get("respondent_document")
            if case.census and document:
                resp = client.post(
                    "/recovery/households",
                    json={
                        "document": document,
                        "manzana_id": manzana,
                        "address": case.address,
                        **case.census,
                    },
                )
                print(
                    "  · Censo RUD: "
                    + (
                        "hogar ya estaba (se reutiliza, sin duplicar)"
                        if resp.status_code == 200
                        else f"planilla {case.census['census_form_number']} registrada"
                        if resp.status_code == 201
                        else f"✗ {resp.status_code} {resp.text}"
                    )
                )
                household = resp.json().get("household", {})
                if household.get("id"):
                    client.patch(
                        f"/recovery/households/{household['id']}/rud",
                        params={"rud_status": "inscrito"},
                    ).raise_for_status()
                    print("  · Hogar inscrito en el RUD")

            for aid in case.aids:
                payload = {
                    "document": document,
                    "delivered_by": "Cruz Roja Colombiana Seccional Caldas",
                    "signed": True,
                    **{k: v for k, v in aid.items() if k != "shelter"},
                }
                if aid.get("shelter"):
                    used_shelter = _shelter(client, case.review["residents"])
                    payload["shelter_id"] = used_shelter["id"]
                justification = payload.pop("justification", None)
                resp = client.post("/recovery/aid", json=payload)
                if resp.status_code == 409 and justification:
                    print(f"  · Acta {aid['act_number']}: bloqueada por repetida → se justifica")
                    resp = client.post(
                        "/recovery/aid", json={**payload, "justification": justification}
                    )
                if resp.status_code != 201:
                    print(f"  ✗ acta {aid['act_number']}: {resp.status_code} {resp.text}")
                    return 1
                out = resp.json()
                where = f" en {out['shelter_name']}" if out.get("shelter_name") else ""
                print(f"  · Acta N.º {out['act_number']}: {AID_LABEL[out['aid_type']]}{where}")

            if case.referrals_done:
                with httpx.Client(
                    base_url=API_BASE_URL,
                    headers={"Authorization": f"Bearer {TOKEN_AGENCIA}"},
                    timeout=30,
                ) as agency:
                    for entity in case.referrals_done:
                        agency.patch(
                            f"/recovery/reviews/{review['id']}/referrals/{entity}",
                            json={"done": True},
                        ).raise_for_status()
                        print(f"  · {entity.upper()} marcó su visita como hecha")
            print(f"  ⇒ {case.lesson}")

        shelter = used_shelter or _shelter(client, 0)
        client.patch(
            f"/recovery/shelters/{shelter['id']}",
            json={
                "operator": "Secretaría de Desarrollo Social · Cruz Roja",
                "services": ["agua", "energia", "banos", "cocina", "zona_mascotas"],
            },
        ).raise_for_status()
        print(f"\nAlbergue {shelter['name']}: entidad administradora y servicios registrados.")
    print("\nListo. Revise el módulo Recuperación siguiendo docs/guia_recuperacion.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
