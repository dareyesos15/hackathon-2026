"""Despacho a agencias (specs/002 US1; contracts/rest-api.md §Despachos, §Agencias y recursos)."""

import uuid

import httpx

from tests.integration.conftest import AGENCIA, COE, PMU, PUBLICO


async def _incident(client: httpx.AsyncClient, body: str, sender: str) -> dict:
    resp = await client.post("/ingest/sms", json={"from": sender, "body": body}, headers=PMU)
    assert resp.status_code == 201, resp.text
    return resp.json()["incident"]


async def _detail(client: httpx.AsyncClient, incident_id: str) -> dict:
    resp = await client.get(f"/incidents/{incident_id}", headers=PMU)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _dispatch(client: httpx.AsyncClient, incident_id: str, resource_ids: list[str], **extra):
    body = {
        "client_uuid": str(uuid.uuid4()),
        "incident_id": incident_id,
        "resource_ids": resource_ids,
    }
    body.update(extra)
    return await client.post("/dispatches", json=body, headers=PMU), body


async def _kpi(client: httpx.AsyncClient) -> dict[str, dict]:
    items = (await client.get("/metrics/kpi", headers=PMU)).json()["items"]
    return {k["indicator"]: k for k in items}


async def test_suggestion_follows_emre_table(client: httpx.AsyncClient) -> None:
    incident = await _incident(client, "DACORA ATR SANCANCIO 2 casa colapsada", "+573005551001")
    suggestion = (await _detail(client, incident["id"]))["suggestion"]
    assert suggestion["emre_function"] == "salvamento_seguridad"
    assert suggestion["emre_function_label"] == "1. Salvamento y seguridad"
    assert suggestion["suggested_agency"]["code"] == "BOMBEROS"
    assert [a["code"] for a in suggestion["alternative_agencies"]] == ["DEFENSA_CIVIL", "POLICIA"]
    candidates = suggestion["candidates"]
    assert candidates and suggestion["fallback_used"] is False
    assert {c["agency_code"] for c in candidates} == {"BOMBEROS"}
    distances = [c["distance_m"] for c in candidates]
    assert distances == sorted(distances)
    assert all(c["source"] == "SIMULADO" for c in candidates)


async def test_dispatch_is_idempotent_and_blocks_double_dispatch(
    client: httpx.AsyncClient,
) -> None:
    incident = await _incident(
        client, "DACORA ATR LA_FLORIDA 3 edificio caido calle 70", "+573005551002"
    )
    candidates = (await _detail(client, incident["id"]))["suggestion"]["candidates"]
    first, second = candidates[0]["resource"]["id"], candidates[1]["resource"]["id"]

    resp, body = await _dispatch(client, incident["id"], [first])
    assert resp.status_code == 201, resp.text
    created = resp.json()["items"][0]
    assert created["status"] == "en_camino"
    assert created["suggested"] is True
    assert created["agency"]["code"] == "BOMBEROS"
    assert created["resource"]["status"] == "en_camino"

    again = await client.post("/dispatches", json=body, headers=PMU)
    assert again.status_code == 200
    assert again.json()["items"][0]["id"] == created["id"]

    before = (await _kpi(client))["double_dispatch_prevented"]["value"]
    blocked, _ = await _dispatch(client, incident["id"], [second])
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "active_dispatch_exists"
    assert blocked.json()["active"][0]["id"] == created["id"]
    assert (await _kpi(client))["double_dispatch_prevented"]["value"] == before + 1

    no_reason, _ = await _dispatch(client, incident["id"], [second], is_reinforcement=True)
    assert no_reason.status_code == 422
    assert no_reason.json()["code"] == "justification_required"

    reinforcement, _ = await _dispatch(
        client,
        incident["id"],
        [second],
        is_reinforcement=True,
        justification="Hay más personas atrapadas, confirmar con 3001234567",
    )
    assert reinforcement.status_code == 201, reinforcement.text
    item = reinforcement.json()["items"][0]
    assert item["is_reinforcement"] is True
    assert "3001234567" not in item["justification"]
    assert "[TEL]" in item["justification"]

    summary = next(
        i
        for i in (await client.get("/incidents", headers=PMU)).json()["items"]
        if i["id"] == incident["id"]
    )
    assert summary["dispatch_status"] == "en_camino"
    assert summary["assigned_agency"] == "Cuerpo Oficial de Bomberos"
    actions = [e["action"] for e in (await _detail(client, incident["id"]))["events"]]
    assert {"despachar", "despacho_doble_bloqueado", "reforzar"} <= set(actions)


async def test_busy_resource_cannot_be_dispatched(client: httpx.AsyncClient) -> None:
    one = await _incident(client, "DACORA INC ARENILLO 0 incendio en casa", "+573005551003")
    two = await _incident(client, "DACORA GAS VERSALLES 0 olor a gas fuerte", "+573005551004")
    resource = (await _detail(client, one["id"]))["suggestion"]["candidates"][0]["resource"]["id"]
    ok, _ = await _dispatch(client, one["id"], [resource])
    assert ok.status_code == 201
    busy, _ = await _dispatch(client, two["id"], [resource])
    assert busy.status_code == 409
    assert busy.json()["code"] == "resource_unavailable"


async def test_tracks_arrival_and_agency_lifecycle(client: httpx.AsyncClient) -> None:
    incident = await _incident(client, "DACORA HER LA_SULTANA 2 heridos por caida", "+573005551005")
    detail = await _detail(client, incident["id"])
    assert detail["suggestion"]["suggested_agency"]["code"] == "CRUZ_ROJA"
    resource = detail["suggestion"]["candidates"][0]["resource"]
    resp, _ = await _dispatch(client, incident["id"], [resource["id"]])
    dispatch = resp.json()["items"][0]

    outside = await client.post(
        f"/resources/{resource['id']}/tracks",
        json={"kind": "control", "lat": 4.6, "lon": -74.08},
        headers=AGENCIA,
    )
    assert outside.status_code == 422
    assert outside.json()["code"] == "out_of_area"

    old = await client.post(
        f"/resources/{resource['id']}/tracks",
        json={"kind": "control", "lat": 5.06, "lon": -75.5, "at": "2026-01-01T00:00:00Z"},
        headers=AGENCIA,
    )
    assert old.status_code == 201
    listed = (await client.get("/resources", headers=PMU)).json()["items"]
    moved = next(r for r in listed if r["id"] == resource["id"])
    assert (moved["lat"], moved["lon"]) != (5.06, -75.5)  # punto viejo: no mueve la posición

    arrival = await client.post(
        f"/resources/{resource['id']}/tracks",
        json={"kind": "llegada", "lat": incident["lat"], "lon": incident["lon"]},
        headers=AGENCIA,
    )
    assert arrival.status_code == 201
    tracks = (await client.get(f"/resources/{resource['id']}/tracks", headers=PMU)).json()["items"]
    assert [t["at"] for t in tracks] == sorted(t["at"] for t in tracks)
    assert {"salida", "llegada"} <= {t["kind"] for t in tracks}

    agency_id = dispatch["agency"]["id"]
    assert (await client.get("/dispatches", headers=AGENCIA)).json()["code"] == "agency_required"
    mine = await client.get(f"/dispatches?agency_id={agency_id}", headers=AGENCIA)
    assert mine.status_code == 200
    assert {d["agency"]["id"] for d in mine.json()["items"]} == {agency_id}
    current = next(d for d in mine.json()["items"] if d["id"] == dispatch["id"])
    assert current["status"] == "en_sitio"
    assert current["arrived_at"] is not None

    forbidden = await client.patch(
        f"/dispatches/{dispatch['id']}", json={"action": "cancelar", "note": "x"}, headers=AGENCIA
    )
    assert forbidden.status_code == 403
    done = await client.patch(
        f"/dispatches/{dispatch['id']}", json={"action": "finalizar"}, headers=AGENCIA
    )
    assert done.status_code == 200
    assert done.json()["status"] == "finalizado"
    assert done.json()["resource"]["status"] == "disponible"
    again = await client.patch(
        f"/dispatches/{dispatch['id']}", json={"action": "llegada"}, headers=AGENCIA
    )
    assert again.status_code == 409
    assert again.json()["code"] == "invalid_transition"


async def test_cancel_requires_note_and_redacts_it(client: httpx.AsyncClient) -> None:
    incident = await _incident(client, "DACORA COL PALERMO 0 muro colapsado", "+573005551006")
    resource = (await _detail(client, incident["id"]))["suggestion"]["candidates"][0]["resource"]
    resp, _ = await _dispatch(client, incident["id"], [resource["id"]])
    dispatch_id = resp.json()["items"][0]["id"]
    missing = await client.patch(
        f"/dispatches/{dispatch_id}", json={"action": "cancelar"}, headers=COE
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "note_required"
    cancelled = await client.patch(
        f"/dispatches/{dispatch_id}",
        json={"action": "cancelar", "note": "Reasignado, avisar a jefe@bomberos.gov.co"},
        headers=COE,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelado"
    assert "jefe@bomberos.gov.co" not in cancelled.json()["close_note"]


async def test_close_attended_and_closed_incident_rejects_dispatch(
    client: httpx.AsyncClient,
) -> None:
    incident = await _incident(
        client, "DACORA DES ALTA_SUIZA 0 deslizamiento talud", "+573005551007"
    )
    confirm = await client.patch(
        f"/incidents/{incident['id']}", json={"action": "confirmar"}, headers=PMU
    )
    assert confirm.status_code == 200
    closed = await client.patch(
        f"/incidents/{incident['id']}", json={"action": "cerrar_atendido"}, headers=COE
    )
    assert closed.status_code == 200
    assert closed.json()["incident"]["status"] == "atendido"
    resource = (await client.get("/resources?status=disponible", headers=PMU)).json()["items"][0]
    late, _ = await _dispatch(client, incident["id"], [resource["id"]])
    assert late.status_code == 422
    assert late.json()["code"] == "incident_closed"


async def test_dispatch_kpis_and_permissions(client: httpx.AsyncClient) -> None:
    kpi = await _kpi(client)
    for key in ("critical_without_dispatch", "median_time_to_dispatch_min"):
        assert kpi[key]["source"] and kpi[key]["cutoff_at"]
    assert kpi["median_time_to_dispatch_min"]["value"] is not None

    agencies = (await client.get("/agencies", headers=AGENCIA)).json()["items"]
    assert len(agencies) == 10
    assert all(a["resources_total"] >= a["resources_available"] for a in agencies)
    assert (await client.get("/agencies", headers=PUBLICO)).status_code == 403
    body = {"client_uuid": str(uuid.uuid4()), "incident_id": str(uuid.uuid4()), "resource_ids": []}
    assert (await client.post("/dispatches", json=body, headers=AGENCIA)).status_code == 403


async def test_simulated_rfid_feed_moves_resource_to_site(client: httpx.AsyncClient) -> None:
    from datetime import UTC, datetime, timedelta

    from app.adapters.tracks import SimulatedRfidFeed
    from app.db import SessionLocal
    from app.routers.dispatch import publish_track

    incident = await _incident(client, "DACORA VIA MARMATO 0 via bloqueada", "+573005551008")
    resource = (await _detail(client, incident["id"]))["suggestion"]["candidates"][0]["resource"]
    resp, _ = await _dispatch(client, incident["id"], [resource["id"]])
    dispatch = resp.json()["items"][0]

    feed = SimulatedRfidFeed(SessionLocal, publish_track, tick_s=5, speedup=20)
    assert await feed.tick(datetime.now(UTC) + timedelta(hours=1)) >= 3  # incluye otros en camino
    assert await feed.tick(datetime.now(UTC) + timedelta(hours=1)) == 0  # ya llegó

    tracks = (await client.get(f"/resources/{resource['id']}/tracks", headers=PMU)).json()["items"]
    mine = [t for t in tracks if t["dispatch_id"] == dispatch["id"]]
    assert [t["kind"] for t in mine] == ["salida", "control", "control", "llegada"]
    assert all(t["origin"] == "rfid_simulado" for t in mine)
    detail = await _detail(client, incident["id"])
    assert detail["dispatches"][0]["status"] == "en_sitio"
    assert detail["dispatch_status"] == "en_sitio"
