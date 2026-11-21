"""Tablero de recuperación unificado contra PostGIS (predios únicos, familias, necesidades)."""

import uuid

import httpx

from .conftest import COE, PMU, PUBLICO


async def _dashboard(client: httpx.AsyncClient) -> dict:
    resp = await client.get("/recovery/dashboard", headers=PMU)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fig(dash: dict, key: str) -> float | None:
    for ind in dash["indicators"]:
        for f in ind["figures"]:
            if f["key"] == key:
                return f["value"]
    raise KeyError(key)


async def test_dashboard_has_ten_traceable_indicators(client: httpx.AsyncClient) -> None:
    dash = await _dashboard(client)
    assert [i["number"] for i in dash["indicators"]] == list(range(1, 11))
    for ind in dash["indicators"]:
        for f in ind["figures"]:
            assert f["source"] and f["cutoff_at"] and f["version"] >= 0
    assert len(dash["stages"]) == 5
    assert len(dash["barrios"]) >= 40
    assert dash["day"] >= 0
    assert (await client.get("/recovery/dashboard", headers=PUBLICO)).status_code == 403
    assert (await client.get("/recovery/dashboard", headers=COE)).status_code == 200


async def test_red_property_family_becomes_a_need_until_housed(
    client: httpx.AsyncClient,
) -> None:
    before = await _dashboard(client)
    manzana = (await client.get("/recovery/manzanas", headers=PMU)).json()[0]["id"]
    address = f"Cra 23 # {uuid.uuid4().int % 90}-{uuid.uuid4().int % 90} prueba"
    prop = {"manzana_id": manzana, "address": address}
    for _ in range(2):  # dos visitas al mismo predio cuentan como un predio
        resp = await client.post(
            "/recovery/inspections",
            headers=PMU,
            json={**prop, "color": "rojo", "damage_level": "mayor"},
        )
        assert resp.status_code == 201, resp.text
    document = str(10_000_000 + uuid.uuid4().int % 89_999_999)
    resp = await client.post(
        "/recovery/households",
        headers=PMU,
        json={**prop, "document": document, "members_count": 4},
    )
    assert resp.status_code == 201, resp.text

    after = await _dashboard(client)
    assert _fig(after, "predios_evaluados") == _fig(before, "predios_evaluados") + 1
    assert (
        _fig(after, "visitas_repetidas_evitadas") == _fig(before, "visitas_repetidas_evitadas") + 1
    )
    assert _fig(after, "familias_sin_solucion") == _fig(before, "familias_sin_solucion") + 1
    assert "familias_sin_solucion" in {n["key"] for n in after["needs"]}

    resp = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={"document": document, "aid_type": "albergue"},
    )
    assert resp.status_code == 201, resp.text
    housed = await _dashboard(client)
    assert _fig(housed, "familias_sin_solucion") == _fig(before, "familias_sin_solucion")
    assert _fig(housed, "familias_albergue") == _fig(before, "familias_albergue") + 1
