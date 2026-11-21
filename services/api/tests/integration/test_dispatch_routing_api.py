"""Destinatarios por incidente, bandeja de la agencia y despacho multiagencia (plan EMRE)."""

import uuid

import httpx

from tests.integration.conftest import AGENCIA, PMU, PUBLICO


async def _incident(client: httpx.AsyncClient, body: str, sender: str) -> dict:
    resp = await client.post("/ingest/sms", json={"from": sender, "body": body}, headers=PMU)
    assert resp.status_code == 201, resp.text
    return resp.json()["incident"]


async def _detail(client: httpx.AsyncClient, incident_id: str) -> dict:
    resp = await client.get(f"/incidents/{incident_id}", headers=PMU)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _plan(client: httpx.AsyncClient, incident_id: str, headers: dict = PMU, **extra):
    body = {"client_uuid": str(uuid.uuid4()), **extra}
    resp = await client.post(f"/incidents/{incident_id}/dispatch-plan", json=body, headers=headers)
    return resp, body


async def _agency_id(client: httpx.AsyncClient, code: str) -> str:
    agencies = (await client.get("/agencies", headers=PMU)).json()["items"]
    return next(a["id"] for a in agencies if a["code"] == code)


async def test_incident_detail_lists_recipients_and_plan(client: httpx.AsyncClient) -> None:
    incident = await _incident(client, "DACORA GAS CHIPRE 4 olor fuerte a gas", "+573005552001")
    routing = (await _detail(client, incident["id"]))["routing"]
    roles = {r["agency"]["code"]: r["role"] for r in routing["recipients"]}
    assert roles["BOMBEROS"] == "lider"
    assert roles["EFIGAS"] == "apoyo"
    assert roles["CHEC"] == "informada"
    assert routing["notify_coe"] is True and routing["held"] is False
    planned = {p["agency"]["code"] for p in routing["plan"] if p["candidate"]}
    # Hay 4 personas en riesgo vital: Cruz Roja entra como apoyo.
    assert planned == {"BOMBEROS", "EFIGAS", "POLICIA", "CRUZ_ROJA"}
    assert len(routing["plan_resource_ids"]) == 4


async def test_service_outage_suggests_the_utility(client: httpx.AsyncClient) -> None:
    incident = await _incident(
        client, "DACORA SER PALERMO 0 sin agua desde el sismo", "+573005552002"
    )
    detail = await _detail(client, incident["id"])
    assert detail["routing"]["recipients"][0]["agency"]["code"] == "AGUAS_MANIZALES"
    assert detail["suggestion"]["suggested_agency"]["code"] == "AGUAS_MANIZALES"


async def test_plan_dispatch_is_multiagency_and_idempotent(client: httpx.AsyncClient) -> None:
    incident = await _incident(
        client, "DACORA GAS LA_ENEA 2 fuga de gas en edificio", "+573005552003"
    )
    resp, body = await _plan(client, incident["id"])
    assert resp.status_code == 201, resp.text
    items = resp.json()["items"]
    assert {d["agency"]["code"] for d in items} == {"BOMBEROS", "EFIGAS", "POLICIA", "CRUZ_ROJA"}
    assert all(not d["is_reinforcement"] for d in items)

    url = f"/incidents/{incident['id']}/dispatch-plan"
    again = await client.post(url, json=body, headers=PMU)
    assert again.status_code == 200
    assert {d["id"] for d in again.json()["items"]} == {d["id"] for d in items}

    routing = (await _detail(client, incident["id"]))["routing"]
    assert routing["plan_resource_ids"] == []
    assert all(p["already_dispatched"] for p in routing["plan"])
    empty, _ = await _plan(client, incident["id"])
    assert empty.status_code == 422
    assert empty.json()["code"] == "empty_plan"


async def test_plan_completes_a_partial_dispatch_as_reinforcement(
    client: httpx.AsyncClient,
) -> None:
    incident = await _incident(client, "DACORA INC CENTRO 0 incendio en local", "+573005552004")
    routing = (await _detail(client, incident["id"]))["routing"]
    bomberos = next(p for p in routing["plan"] if p["agency"]["code"] == "BOMBEROS")
    first = await client.post(
        "/dispatches",
        json={
            "client_uuid": str(uuid.uuid4()),
            "incident_id": incident["id"],
            "resource_ids": [bomberos["candidate"]["resource"]["id"]],
        },
        headers=PMU,
    )
    assert first.status_code == 201, first.text
    rest, _ = await _plan(client, incident["id"])
    assert rest.status_code == 201, rest.text
    items = rest.json()["items"]
    assert items and "BOMBEROS" not in {d["agency"]["code"] for d in items}
    assert all(d["is_reinforcement"] for d in items)
    assert items[0]["justification"].startswith("Completa el plan multiagencia")


async def test_agency_inbox_receives_routed_incidents(client: httpx.AsyncClient) -> None:
    incident = await _incident(
        client, "DACORA ATR VILLA_PILAR 3 personas atrapadas casa", "+573005552005"
    )
    police = await _agency_id(client, "POLICIA")
    resp = await client.get(f"/agencies/{police}/inbox", headers=AGENCIA)
    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["items"] if i["incident"]["id"] == incident["id"])
    assert item["role"] == "apoyo"
    assert item["emre_task"].startswith("1.1")
    assert item["notify_coe"] is True

    social = await _agency_id(client, "SEC_DESARROLLO_SOCIAL")
    other = (await client.get(f"/agencies/{social}/inbox", headers=AGENCIA)).json()["items"]
    assert incident["id"] not in {i["incident"]["id"] for i in other}

    forbidden = await client.get(f"/agencies/{police}/inbox", headers=PUBLICO)
    assert forbidden.status_code == 403


async def test_plan_requires_pmu_or_coe(client: httpx.AsyncClient) -> None:
    incident = await _incident(client, "DACORA DAN MILAN 0 grietas en muro", "+573005552006")
    resp, _ = await _plan(client, incident["id"], headers=AGENCIA)
    assert resp.status_code == 403
