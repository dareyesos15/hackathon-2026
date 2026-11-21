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


async def test_dashboard_never_invents_figures(client: httpx.AsyncClient) -> None:
    dash = await _dashboard(client)
    figures = [f for i in dash["indicators"] for f in i["figures"]]
    figures += [f for s in dash["stages"] for f in s["figures"]]
    for f in figures:
        if f["state"] == "sin_fuente":
            assert f["value"] is None and f["note"], f["key"]
    # Las fuentes públicas conectadas traen respaldo íntegro (URL, licencia y huella).
    for src in dash["sources"]:
        if src["key"] in {"usgs", "secop"} and src["status"] == "conectada":
            assert src["verified"] and src["query_url"] and src["license"] and src["sha256"]
    # Lo que no tiene acceso público queda nombrado, no estimado.
    assert {s["key"] for s in dash["sources"] if s["status"] == "sin_convenio"} >= {
        "servicios",
        "economia",
        "finanzas",
    }
    # Una etapa sin dato de avance no recibe semáforo inventado.
    for stage in dash["stages"]:
        if stage["progress_pct"] is None and stage["start_day"] <= dash["day"]:
            assert stage["status"] == "sin_fuente"
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

    from app.db import SessionLocal
    from app.seed import seed_shelters

    async with SessionLocal() as session:
        await seed_shelters(session)
    shelters = (await client.get("/recovery/shelters", headers=PMU)).json()["items"]
    shelter = max(shelters, key=lambda x: x["capacity"] - x["people"])
    resp = await client.post(
        "/recovery/aid",
        headers=PMU,
        json={"document": document, "aid_type": "albergue", "shelter_id": shelter["id"]},
    )
    assert resp.status_code == 201, resp.text
    housed = await _dashboard(client)
    assert _fig(housed, "familias_sin_solucion") == _fig(before, "familias_sin_solucion")
    assert _fig(housed, "familias_albergue") == _fig(before, "familias_albergue") + 1


async def test_scenarios_compare_confidence(client: httpx.AsyncClient) -> None:
    resp = await client.get("/recovery/scenarios", headers=PMU)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    by_key = {s["key"]: s for s in data["scenarios"]}
    best = {s["key"]: s for s in by_key["mejor"]["stats"]}["confianza"]
    worst = {s["key"]: s for s in by_key["peor"]["stats"]}["confianza"]
    assert best["p5"] > worst["p95"]
    assert by_key["mejor"]["runs"] == by_key["peor"]["runs"] >= 1000
    assert (await client.get("/recovery/scenarios", headers=PUBLICO)).status_code == 403


async def test_scenario_dashboard_is_fully_marked_simulated(client: httpx.AsyncClient) -> None:
    for key in ("mejor", "peor"):
        resp = await client.get(f"/recovery/dashboard?scenario={key}", headers=PMU)
        assert resp.status_code == 200, resp.text
        dash = resp.json()
        assert dash["scenario"] == key and "SIMULADO" in dash["scenario_note"]
        figures = [f for i in dash["indicators"] for f in i["figures"]]
        assert [i["number"] for i in dash["indicators"]] == list(range(1, 11))
        # Todo lo del escenario va marcado; solo el día del evento viene del USGS real.
        for f in figures:
            if f["key"] != "dias_desde_evento":
                assert f["simulated"], f["key"]
    best = (await client.get("/recovery/dashboard?scenario=mejor", headers=PMU)).json()
    worst = (await client.get("/recovery/dashboard?scenario=peor", headers=PMU)).json()
    missing = lambda d: sum(  # noqa: E731
        f["state"] == "sin_fuente" for i in d["indicators"] for f in i["figures"]
    )
    assert missing(worst) > missing(best)
