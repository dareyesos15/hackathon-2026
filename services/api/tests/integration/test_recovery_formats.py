"""Censo (RUD), actas de entrega y albergues: el flujo completo sin datos personales."""

import csv
import io
import uuid

import httpx

from .conftest import PMU


def _doc() -> str:
    return str(990_000_000 + uuid.uuid4().int % 9_999_999)


async def _shelter(client: httpx.AsyncClient) -> dict:
    from app.db import SessionLocal
    from app.seed import seed_shelters

    async with SessionLocal() as session:
        await seed_shelters(session)
    items = (await client.get("/recovery/shelters", headers=PMU)).json()["items"]
    return max(items, key=lambda s: s["capacity"] - s["people"])


async def test_census_records_rud_fields_and_rejects_repeated_form(
    client: httpx.AsyncClient,
) -> None:
    number = str(uuid.uuid4().int % 10**9)
    body = {
        "document": _doc(),
        "members_count": 5,
        "census_form_number": number,
        "tenure": "arrendatario",
        "age_0_5": 1,
        "age_6_17": 1,
        "age_18_59": 2,
        "age_60_plus": 1,
        "female_members": 3,
        "losses": ["enseres", "herramientas_trabajo"],
    }
    resp = await client.post("/recovery/households", headers=PMU, json=body)
    assert resp.status_code == 201, resp.text
    out = resp.json()["household"]
    assert out["census_form_number"] == number and out["tenure"] == "arrendatario"
    again = await client.post(
        "/recovery/households", headers=PMU, json={**body, "document": _doc()}
    )
    assert again.status_code == 409
    bad = await client.post(
        "/recovery/households",
        headers=PMU,
        json={"document": _doc(), "members_count": 2, "age_18_59": 3},
    )
    assert bad.status_code == 422

    csv_text = (await client.get("/recovery/households/export.csv", headers=PMU)).text
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    mine = next(r for r in rows if r["planilla_censo"] == number)
    assert mine["tenencia"] == "arrendatario" and mine["edad_60_mas"] == "1"
    assert mine["perdidas"] == "enseres|herramientas_trabajo"


async def test_shelter_stay_moves_occupancy_and_family_situation(
    client: httpx.AsyncClient,
) -> None:
    shelter = await _shelter(client)
    document = _doc()
    created = await client.post(
        "/recovery/households",
        headers=PMU,
        json={"document": document, "members_count": 3, "pets_count": 1},
    )
    assert created.status_code == 201, created.text

    no_shelter = await client.post(
        "/recovery/aid", headers=PMU, json={"document": document, "aid_type": "albergue"}
    )
    assert no_shelter.status_code == 422

    act = str(uuid.uuid4().int % 10**9)
    stay = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={
            "document": document,
            "aid_type": "albergue",
            "shelter_id": shelter["id"],
            "act_number": act,
            "delivered_by": "Cruz Roja Colombiana",
            "signed": True,
        },
    )
    assert stay.status_code == 201, stay.text
    after = next(
        s
        for s in (await client.get("/recovery/shelters", headers=PMU)).json()["items"]
        if s["id"] == shelter["id"]
    )
    assert after["people"] == shelter["people"] + 3 and after["pets"] == shelter["pets"] + 1
    assert after["families"] == shelter["families"] + 1

    twice = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={"document": document, "aid_type": "albergue", "shelter_id": shelter["id"]},
    )
    assert twice.status_code == 409
    same_act = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={"document": document, "aid_type": "kit", "act_number": act},
    )
    assert same_act.status_code == 409

    lookup = (
        await client.post("/recovery/households/lookup", headers=PMU, json={"document": document})
    ).json()
    assert lookup["situation"] == "albergue"

    ended = await client.post(f"/recovery/aid/{stay.json()['id']}/end", headers=PMU)
    assert ended.status_code == 200 and ended.json()["ended_at"]
    back = next(
        s
        for s in (await client.get("/recovery/shelters", headers=PMU)).json()["items"]
        if s["id"] == shelter["id"]
    )
    assert back["people"] == shelter["people"] and back["families"] == shelter["families"]


async def test_rent_subsidy_requires_amount_and_months(client: httpx.AsyncClient) -> None:
    document = _doc()
    await client.post(
        "/recovery/households", headers=PMU, json={"document": document, "members_count": 2}
    )
    missing = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={"document": document, "aid_type": "subsidio_arriendo"},
    )
    assert missing.status_code == 422
    ok = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={
            "document": document,
            "aid_type": "subsidio_arriendo",
            "amount_cop": 550000,
            "months": 3,
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["amount_cop"] == 550000 and ok.json()["months"] == 3


async def test_census_completes_a_household_that_came_from_a_review(
    client: httpx.AsyncClient,
) -> None:
    document = _doc()
    first = await client.post(
        "/recovery/households", headers=PMU, json={"document": document, "members_count": 3}
    )
    assert first.status_code == 201
    number = str(uuid.uuid4().int % 10**9)
    second = await client.post(
        "/recovery/households",
        headers=PMU,
        json={
            "document": document,
            "members_count": 3,
            "census_form_number": number,
            "tenure": "propietario",
            "age_18_59": 2,
            "age_60_plus": 1,
            "losses": ["enseres"],
        },
    )
    assert second.status_code == 200, second.text
    out = second.json()["household"]
    assert out["id"] == first.json()["household"]["id"]
    assert out["census_form_number"] == number and out["tenure"] == "propietario"
    assert out["age_60_plus"] == 1 and out["losses"] == ["enseres"]
