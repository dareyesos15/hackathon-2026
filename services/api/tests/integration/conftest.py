"""Base de pruebas: se crea, se migra y se carga la geografía una vez por sesión."""

import asyncio
import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio

API_DIR = Path(__file__).resolve().parents[2]


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _ensure_database(url: str) -> None:
    head, _, name = _dsn(url).rpartition("/")
    conn = await asyncpg.connect(f"{head}/postgres")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def database() -> str:
    url = os.environ["DATABASE_URL"]
    try:
        asyncio.run(_ensure_database(url))
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"PostgreSQL no disponible para pruebas de integración: {exc}")
    subprocess.run(["alembic", "upgrade", "head"], cwd=API_DIR, check=True, env=os.environ)
    return url


@pytest_asyncio.fixture(scope="session")
async def client(database: str) -> AsyncIterator[httpx.AsyncClient]:
    from app.db import SessionLocal
    from app.main import app
    from app.seed import seed_geography
    from app.state import load_state

    async with SessionLocal() as session:
        await seed_geography(session)
        await load_state(session)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


PMU = {"Authorization": "Bearer pmu-demo"}
CIUDADANO = {"Authorization": "Bearer ciudadano-demo"}
