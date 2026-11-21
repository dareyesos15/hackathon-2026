"""Revisión a predio: un formato alimenta habitabilidad, censo y derivaciones (sin PII)."""

import uuid

import httpx
from sqlalchemy import text

from .conftest import AGENCIA, PMU, PUBLICO


async def _manzana(client: httpx.AsyncClient) -> str:
    return (await client.get("/recovery/manzanas", headers=PMU)).json()[0]["id"]


def _form(manzana: str, **extra: object) -> dict:
    n = uuid.uuid4().int
    return {
        "manzana_id": manzana,
        "address": f"Cra 23 # {n % 90}-{(n // 90) % 90} formato",
        "form_number": str(n % 10**9),
        "event_types": ["sismo"],
        "affectation": "parcial",
        **extra,
    }


async def test_review_feeds_semaphore_census_and_referrals(client: httpx.AsyncClient) -> None:
    manzana = await _manzana(client)
    document = str(10_000_000 + uuid.uuid4().int % 89_999_999)
    body = _form(
        manzana,
        respondent_document=document,
        respondent_relation="arrendatario",
        owner_document="75123456",
        residents=4,
        minors=1,
        elderly=1,
        evacuation_recommended=True,
        referrals=["ugr", "aguas_de_manizales"],
        belongings_loss="me llamo Ana Gómez, nevera y camas 3001234567",
    )
    resp = await client.post("/recovery/reviews", headers=PMU, json=body)
    assert resp.status_code == 201, resp.text
    out = resp.json()
    # Evacuación recomendada ⇒ semáforo rojo sugerido y aplicado.
    assert out["color"] == "rojo" and out["suggested_color"] == "rojo"
    assert out["household_created"] and out["household_code"]
    assert any("Cruz Roja" in s for s in out["next_steps"])
    # Los textos libres se redactan; el documento del propietario no se guarda.
    assert "Ana" not in (out["belongings_loss"] or "")
    assert "3001234567" not in (out["belongings_loss"] or "")

    # El mismo formato no se puede registrar dos veces.
    again = await client.post("/recovery/reviews", headers=PMU, json=body)
    assert again.status_code == 409

    # Una segunda revisión del mismo hogar lo liga sin duplicarlo.
    second = _form(
        manzana,
        address=body["address"],
        respondent_document=document,
        affectation="total",
    )
    resp2 = await client.post("/recovery/reviews", headers=PMU, json=second)
    assert resp2.status_code == 201, resp2.text
    assert not resp2.json()["household_created"]
    assert resp2.json()["visit_number"] == 2

    # Derivaciones: pendientes hasta que la entidad marque su visita.
    refs = (await client.get("/recovery/referrals", headers=AGENCIA)).json()
    mine = [r for r in refs["pending"] if r["review_id"] == out["id"]]
    assert {r["entity"] for r in mine} == {"ugr", "aguas_de_manizales"}
    done = await client.patch(
        f"/recovery/reviews/{out['id']}/referrals/ugr", headers=AGENCIA, json={"done": True}
    )
    assert done.status_code == 200 and done.json()["done"] == 1
    refs = (await client.get("/recovery/referrals", headers=PMU)).json()
    assert {r["entity"] for r in refs["pending"] if r["review_id"] == out["id"]} == {
        "aguas_de_manizales"
    }
    bad = await client.patch(
        f"/recovery/reviews/{out['id']}/referrals/chec", headers=PMU, json={"done": True}
    )
    assert bad.status_code == 422


async def test_incoherent_review_is_rejected(client: httpx.AsyncClient) -> None:
    manzana = await _manzana(client)
    resp = await client.post(
        "/recovery/reviews",
        headers=PMU,
        json=_form(
            manzana,
            evacuation_recommended=True,
            color="amarillo",
            damage_level="mediano_uso_restringido",
        ),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "inconsistent_review"
    public = await client.post("/recovery/reviews", headers=PUBLICO, json=_form(manzana))
    assert public.status_code == 403


async def test_no_personal_data_is_stored(client: httpx.AsyncClient) -> None:
    from app.db import SessionLocal

    manzana = await _manzana(client)
    body = _form(manzana, respondent_document="98765432", owner_document="12345678", residents=2)
    assert (await client.post("/recovery/reviews", headers=PMU, json=body)).status_code == 201
    async with SessionLocal() as session:
        dump = (
            (await session.execute(text("SELECT row_to_json(r)::text FROM property_reviews r")))
            .scalars()
            .all()
        )
    blob = " ".join(dump)
    assert "98765432" not in blob and "12345678" not in blob
