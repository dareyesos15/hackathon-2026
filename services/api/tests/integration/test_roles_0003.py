"""Migración 0003, catálogo sembrado, permisos de los roles `coe`/`agencia` y reinicio (specs/002).

Se ejecuta al final de la suite (orden alfabético): el downgrade borra las tablas nuevas.
"""

import asyncio
import os
import subprocess

import httpx
from sqlalchemy import func, select, text

from app.db import SessionLocal
from app.models import Agency, Resource
from app.routers.stream import AGENCY_EVENTS
from app.seed import seed_catalog
from tests.integration.conftest import AGENCIA, API_DIR, COE, PMU, PUBLICO


async def test_catalog_is_seeded(client: httpx.AsyncClient) -> None:
    async with SessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(Agency)) == 10
        assert await session.scalar(select(func.count()).select_from(Resource)) == 24
        sources = set((await session.execute(select(Resource.source))).scalars())
    assert sources == {"SIMULADO"}


async def test_coe_reads_incidents_map_and_kpi(client: httpx.AsyncClient) -> None:
    for path in ("/incidents", "/map/manzanas", "/metrics/kpi"):
        resp = await client.get(path, headers=COE)
        assert resp.status_code == 200, (path, resp.text)


async def test_agency_and_public_cannot_read_incidents(client: httpx.AsyncClient) -> None:
    assert (await client.get("/incidents", headers=AGENCIA)).status_code == 403
    assert (await client.get("/incidents", headers=PUBLICO)).status_code == 403


async def test_coe_can_review_incident(client: httpx.AsyncClient) -> None:
    sms = await client.post(
        "/ingest/sms",
        json={"from": "+573005559001", "body": "DACORA INC GALAN 0 incendio en bodega cra 18"},
        headers=PMU,
    )
    incident_id = sms.json()["incident"]["id"]
    resp = await client.patch(
        f"/incidents/{incident_id}", json={"action": "confirmar"}, headers=COE
    )
    assert resp.status_code == 200
    assert resp.json()["events"][0]["actor_role"] == "coe"


def test_agency_stream_only_gets_dispatch_events() -> None:
    assert {"dispatch.upserted", "resource.moved"} == AGENCY_EVENTS


async def test_demo_reset_returns_resources_to_base(client: httpx.AsyncClient) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text(
                "UPDATE resources SET status = 'en_camino',"
                " last_geom = ST_SetSRID(ST_MakePoint(-75.5, 5.06), 4326)"
            )
        )
        await session.commit()
    assert (await client.post("/demo/reset", headers=PMU)).status_code == 204
    async with SessionLocal() as session:
        moved = await session.scalar(
            select(func.count())
            .select_from(Resource)
            .where(
                (Resource.status != "disponible")
                | ~func.ST_Equals(Resource.last_geom, Resource.base_geom)
            )
        )
    assert moved == 0


async def test_migration_0003_round_trip(client: httpx.AsyncClient) -> None:
    env = dict(os.environ)
    for target in ("0002", "head"):
        cmd = ["alembic", "downgrade" if target == "0002" else "upgrade", target]
        await asyncio.to_thread(
            subprocess.run, cmd, cwd=API_DIR, check=True, env=env, capture_output=True
        )
    async with SessionLocal() as session:
        await seed_catalog(session)
        assert await session.scalar(select(func.count()).select_from(Resource)) == 24
