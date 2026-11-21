"""Dacora API (servicio principal `api`). REST bajo /api/v1; contrato en /openapi.json."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.adapters.rain import rain_feed
from app.adapters.tracks import SimulatedRfidFeed
from app.adapters.zone_sensor import SimulatedZoneSensorFeed
from app.config import get_settings
from app.db import SessionLocal
from app.routers import (
    alerts,
    auth,
    cascade,
    demo,
    dispatch,
    incident_admin,
    incidents,
    ingest,
    map,
    mass_alerts,
    metrics,
    recovery,
    recovery_dashboard,
    recovery_reviews,
    recovery_scenarios,
    reports,
    review,
    sms_gateway,
    stream,
    zone_sensors,
)
from app.seed import seed_catalog, seed_geography, seed_shelters, seed_zone_sensors
from app.state import load_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dacora")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as session:
        await seed_geography(session)
        await seed_catalog(session)
        await seed_shelters(session)
        await seed_zone_sensors(session)
        await load_state(session)
    settings = get_settings()
    log.info("Dacora API lista (similitud: %s)", settings.similarity_provider)
    feed_task: asyncio.Task[None] | None = None
    if settings.simulate_tracks:
        feed = SimulatedRfidFeed(
            SessionLocal,
            dispatch.publish_track,
            tick_s=settings.track_tick_s,
            speedup=settings.track_speedup,
        )
        feed_task = asyncio.create_task(feed.run())
    zone_task: asyncio.Task[None] | None = None
    if settings.simulate_zone_sensors:

        async def process(session, sensor, reading, now):  # type: ignore[no-untyped-def]
            return await zone_sensors.process_reading(
                session, ingest.get_engine(), sensor, reading, now
            )

        zone_task = asyncio.create_task(
            SimulatedZoneSensorFeed(SessionLocal, process, tick_s=settings.zone_tick_s).run()
        )
    rain_task = asyncio.create_task(rain_feed.run(SessionLocal, cascade.rain_changed))
    log.info("Fuente de lluvia de la cascada: %s", rain_feed.source.value)
    yield
    for task in (feed_task, zone_task, rain_task):
        if task is not None:
            task.cancel()


app = FastAPI(
    title="Dacora API",
    version=get_settings().app_version,
    description=(
        "Ingesta multicanal, motor de verificación (Habeas Data, triaje, deduplicación, "
        "trust score) y tablero del PMU. Prototipo Hackathon UNAL Manizales 2026. "
        "Datos SIMULADOS."
    ),
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    detail: Any = exc.detail
    body = detail if isinstance(detail, dict) else {"detail": str(detail), "code": "error"}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Datos inválidos en la solicitud",
            "code": "validation_error",
            "errors": [
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()
            ],
        },
    )


class Health(BaseModel):
    status: str
    db: str
    similarity_provider: str
    version: str


health_router = APIRouter(tags=["salud"])


@health_router.get("/health", response_model=Health)
async def health() -> Health:
    db_status = "ok"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - la salud reporta, no falla
        db_status = "error"
    settings = get_settings()
    return Health(
        status="ok" if db_status == "ok" else "degraded",
        db=db_status,
        similarity_provider=settings.similarity_provider,
        version=settings.app_version,
    )


app.include_router(health_router, prefix=API_PREFIX)
for module in (
    auth,
    ingest,
    sms_gateway,
    reports,
    incidents,
    review,
    dispatch,
    alerts,
    mass_alerts,
    incident_admin,
    cascade,
    map,
    stream,
    metrics,
    recovery,
    recovery_dashboard,
    recovery_reviews,
    recovery_scenarios,
    zone_sensors,
    demo,
):
    app.include_router(module.router, prefix=API_PREFIX)
