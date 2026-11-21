"""Idempotencia, reglas de ingesta y rendimiento < 1 s (FR-005, FR-021, SC-005)."""

import random
import statistics
import uuid

import httpx
import pytest

from tests.integration.conftest import CIUDADANO, PMU


def pwa_report(**kw: object) -> dict[str, object]:
    body: dict[str, object] = {
        "client_uuid": str(uuid.uuid4()),
        "channel": "pwa",
        "text": "se cayó una pared en Chipre",
        "barrio": "Chipre",
        "consent": True,
    }
    body.update(kw)
    return body


async def test_report_is_idempotent(client: httpx.AsyncClient) -> None:
    body = pwa_report(reporter_contact="3001112233")
    first = await client.post("/ingest/report", json=body, headers=CIUDADANO)
    second = await client.post("/ingest/report", json=body, headers=CIUDADANO)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["report"]["id"] == second.json()["report"]["id"]
    assert second.json()["created"] is False


async def test_batch_is_idempotent(client: httpx.AsyncClient) -> None:
    items = [pwa_report(), pwa_report(text="huele a gas en Palermo", barrio="Palermo")]
    first = await client.post("/ingest/batch", json={"items": items}, headers=CIUDADANO)
    second = await client.post("/ingest/batch", json={"items": items}, headers=CIUDADANO)
    assert [r["status"] for r in first.json()["results"]] == ["created", "created"]
    assert [r["status"] for r in second.json()["results"]] == ["duplicate", "duplicate"]


async def test_batch_item_error_does_not_fail_batch(client: httpx.AsyncClient) -> None:
    items = [pwa_report(consent=False), pwa_report()]
    resp = await client.post("/ingest/batch", json={"items": items}, headers=CIUDADANO)
    assert [r["status"] for r in resp.json()["results"]] == ["error", "created"]


async def test_consent_is_required(client: httpx.AsyncClient) -> None:
    resp = await client.post("/ingest/report", json=pwa_report(consent=False), headers=CIUDADANO)
    assert resp.status_code == 422
    assert resp.json()["code"] == "consent_required"


async def test_citizen_cannot_inject_entity_channel(client: httpx.AsyncClient) -> None:
    resp = await client.post("/ingest/report", json=pwa_report(channel="entity"), headers=CIUDADANO)
    assert resp.status_code == 403


async def test_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.post("/ingest/report", json=pwa_report())
    assert resp.status_code == 401


async def test_malformed_sms_is_never_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/ingest/sms", json={"from": "+573001110000", "body": "hola"}, headers=PMU
    )
    assert resp.status_code == 201
    report = resp.json()["report"]
    assert report["category"] == "sin_clasificar"
    assert report["status"] == "en_revision"


async def test_processing_under_one_second(client: httpx.AsyncClient) -> None:
    rng = random.Random(7)
    texts = [
        "hay gente atrapada en el edificio",
        "huele a gas",
        "sin luz en el barrio",
        "grietas en las columnas",
        "necesitamos agua y comida",
        "se sintió muy fuerte",
        "via bloqueada por escombros",
        "incendio en la bodega",
    ]
    barrios = ["Centro", "Milán", "Chipre", "Palermo", "La Enea", "San José", "Villa Pilar"]
    times = []
    for _ in range(100):
        body = pwa_report(text=rng.choice(texts), barrio=rng.choice(barrios))
        resp = await client.post("/ingest/report", json=body, headers=CIUDADANO)
        assert resp.status_code == 201
        times.append(resp.json()["processing_ms"])
    p95 = statistics.quantiles(times, n=20)[18]
    assert p95 < 1000, f"p95 = {p95} ms"


async def test_gps_report_is_placed_exactly_at_its_point(client: httpx.AsyncClient) -> None:
    """El GPS manda: el incidente queda en el punto exacto y el barrio sale de la manzana."""
    lat, lon = 5.04590, -75.47986  # Milán (OpenStreetMap)
    by_barrio = await client.post(
        "/ingest/report",
        json=pwa_report(text="se cayó una casa en Milán", barrio="Milán"),
        headers=CIUDADANO,
    )
    assert by_barrio.status_code == 201

    gps = await client.post(
        "/ingest/report",
        json=pwa_report(
            text="se cayó una casa, hay gente adentro",
            barrio=None,
            location={"lat": lat, "lon": lon, "precision": "gps"},
        ),
        headers=CIUDADANO,
    )
    assert gps.status_code == 201
    report = gps.json()["report"]
    assert report["geo_precision"] == "gps"
    assert (report["lat"], report["lon"]) == (lat, lon)
    assert report["barrio"] == "Milán"

    incident = await client.get(f"/incidents/{report['incident_id']}", headers=PMU)
    assert incident.status_code == 200
    body = incident.json()
    assert body["lat"] == pytest.approx(lat, abs=1e-6)
    assert body["lon"] == pytest.approx(lon, abs=1e-6)
