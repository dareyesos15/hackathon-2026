"""La IA solo sugiere; decide un humano (principio III, FR-013, FR-025)."""

import uuid

import httpx

from tests.integration.conftest import CIUDADANO, PMU


async def _sms(client: httpx.AsyncClient, body: str, sender: str) -> dict:
    resp = await client.post("/ingest/sms", json={"from": sender, "body": body}, headers=PMU)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_system_never_discards_life_threat(client: httpx.AsyncClient) -> None:
    # Riesgo vital con lenguaje de cadena: puntaje bajo, pero sigue en revisión humana.
    data = await _sms(
        client, "reenvia dicen que hay atrapados en el Coliseo Mayor", "+573005550001"
    )
    assert data["report"]["is_life_threat"] is True
    assert data["report"]["status"] == "en_revision"
    assert data["incident"]["trust_label"] == "posible_falso"


async def test_discarding_life_threat_requires_note(client: httpx.AsyncClient) -> None:
    data = await _sms(
        client, "DACORA ATR LA_LINDA 2 casa caida calle 11 con carrera 3", "+573005550002"
    )
    incident_id = data["incident"]["id"]
    resp = await client.patch(
        f"/incidents/{incident_id}", json={"action": "descartar"}, headers=PMU
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "note_required_for_life_threat"

    ok = await client.patch(
        f"/incidents/{incident_id}",
        json={"action": "descartar", "note": "Bomberos verificó: sin personas"},
        headers=PMU,
    )
    assert ok.status_code == 200
    assert ok.json()["incident"]["status"] == "descartado"
    assert ok.json()["events"][0]["actor_role"] == "operador_pmu"


async def test_confirm_and_audit_log_is_append_only(client: httpx.AsyncClient) -> None:
    data = await _sms(
        client, "DACORA INC SOLFERINO 0 incendio bodega calle 50 con carrera 30", "+573005550003"
    )
    incident_id = data["incident"]["id"]
    resp = await client.patch(
        f"/incidents/{incident_id}", json={"action": "confirmar"}, headers=PMU
    )
    assert resp.status_code == 200
    assert resp.json()["incident"]["status"] == "verificado"

    again = await client.patch(
        f"/incidents/{incident_id}", json={"action": "confirmar"}, headers=PMU
    )
    assert again.status_code == 409

    detail = (await client.get(f"/incidents/{incident_id}", headers=PMU)).json()
    actions = [e["action"] for e in detail["events"]]
    assert actions[0] == "ingerido"
    assert "confirmar" in actions
    assert data["report"]["id"] in {r["id"] for r in detail["reports"]}


async def test_reopen_and_mark_duplicate_into_other_incident(client: httpx.AsyncClient) -> None:
    a = await _sms(client, "DACORA DAN MARMATO 0 grietas calle 99 con carrera 9", "+573005550004")
    b = await _sms(
        client, "DACORA DAN BOSQUES_DEL_NORTE 0 muro caido calle 12 con carrera 2", "+573005550005"
    )
    resp = await client.patch(
        f"/reports/{b['report']['id']}",
        json={"action": "marcar_duplicado", "duplicate_of_incident": a["incident"]["id"]},
        headers=PMU,
    )
    assert resp.status_code == 200
    assert resp.json()["incident"]["id"] == a["incident"]["id"]
    assert resp.json()["incident"]["report_count"] == a["incident"]["report_count"] + 1

    reopen = await client.patch(
        f"/reports/{b['report']['id']}", json={"action": "reabrir"}, headers=PMU
    )
    assert reopen.status_code == 200
    assert reopen.json()["report"]["status"] == "en_revision"


async def test_only_operator_can_review(client: httpx.AsyncClient) -> None:
    resp = await client.patch(
        f"/incidents/{uuid.uuid4()}", json={"action": "confirmar"}, headers=CIUDADANO
    )
    assert resp.status_code == 403
