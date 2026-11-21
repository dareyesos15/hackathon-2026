"""Utilidades exclusivas de la demo (datos SIMULADOS). Desactivables con DEMO_MODE=false.

El rol `admin` maneja las simulaciones desde la interfaz:
- **con datos:** reinicia y reproduce el escenario sintético (scripts/replay_scenario.py, que es
  un cliente más de esta API REST; principio X), con lluvia SIMULADA opcional;
- **sin datos:** deja todo vacío para una demo en vivo con reportes reales de la sala.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.event_bus import bus
from app.adapters.rain import rain_feed
from app.auth import require_role
from app.config import get_settings
from app.core import cascade
from app.db import get_session
from app.domain import Role

router = APIRouter(prefix="/demo", tags=["demo"])
log = logging.getLogger("dacora.seed")


def _require_demo() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Simulaciones deshabilitadas fuera de modo demo",
                "code": "forbidden",
            },
        )


async def _reset(session: AsyncSession) -> None:
    """Reinicio de la simulación "sin datos": deja todo vacío, sin casos de ejemplo."""
    await _truncate(session)


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_demo_data(
    _: Role = Depends(require_role(Role.operador_pmu, Role.admin)),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Borra reportes, incidentes, despachos, alertas, lluvia, bitácora y métricas.

    Conserva la geografía. Solo existe en modo demo: en producción los reportes son solo-agregar.
    """
    if not get_settings().demo_mode:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"detail": "Reinicio deshabilitado fuera de modo demo", "code": "forbidden"},
        )
    await _truncate(session)
    schedule_recovery_examples("reinicio de la demo")


async def _truncate(session: AsyncSession) -> None:
    await session.execute(
        text(
            "TRUNCATE report_events, resource_tracks, dispatches, alert_events, alert_deliveries,"
            " alerts, rain_readings, reports, incidents, metrics_snapshots,"
            " aid_deliveries, household_vulnerability, households, building_inspections,"
            " zone_sensor_events, mass_alerts CASCADE"
        )
    )
    # Sensores de zonas inseguras: se conservan los sembrados; los instalados en incidentes no.
    await session.execute(text("DELETE FROM zone_sensors WHERE incident_id IS NOT NULL"))
    await session.execute(text("UPDATE zone_sensors SET battery_pct = 100, last_seen_at = NULL"))
    # El catálogo se conserva; los recursos vuelven a su base (research R16).
    await session.execute(
        text(
            "UPDATE resources SET status = 'disponible', last_geom = base_geom, last_seen_at = NULL"
        )
    )
    await session.execute(text("UPDATE shelters SET people = 0, pets = 0, updated_at = now()"))
    await session.commit()
    cascade.invalidate()
    rain_feed.forget()  # con fuente CDIAC, vuelve a consultar sin esperar al siguiente ciclo
    bus.publish("demo.reset", {})


# ------------------------------------------------------------------ casos de recuperación

SEED_SCRIPT = "seed_recovery_example.py"
_seed_lock = asyncio.Lock()
_seed_tasks: set[asyncio.Task[None]] = set()


def schedule_recovery_examples(reason: str) -> None:
    """Carga en segundo plano los casos de ejemplo de recuperación (si está activado).

    El script es un cliente más de la API REST (principio X) e idempotente: si los casos ya
    existen no hace nada. Se espera a que la API responda antes de correrlo.
    """
    settings = get_settings()
    if not (settings.demo_mode and settings.seed_recovery_examples):
        return
    task = asyncio.create_task(_run_recovery_examples(reason))
    _seed_tasks.add(task)
    task.add_done_callback(_seed_tasks.discard)


async def _api_ready(base: str, timeout_s: float = 90.0) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    async with httpx.AsyncClient(timeout=2.0) as client:
        while loop.time() < deadline:
            try:
                if (await client.get(f"{base}/health")).status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1.0)
    return False


async def _run_recovery_examples(reason: str) -> None:
    async with _seed_lock:
        settings = get_settings()
        base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
        if not await _api_ready(base):
            log.warning("Casos de recuperación (%s): la API no respondió a tiempo", reason)
            return
        try:
            scripts = _scripts_dir()
        except HTTPException:
            log.warning("Casos de recuperación (%s): no se encontró la carpeta scripts", reason)
            return
        env = {
            **os.environ,
            "API_BASE_URL": base,
            "TOKEN_OPERADOR_PMU": settings.token_operador_pmu,
            "TOKEN_AGENCIA": settings.token_agencia,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        }
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(scripts / SEED_SCRIPT),
            cwd=str(scripts),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await process.communicate()
        lines = [x for x in output.decode("utf-8", errors="replace").splitlines() if x.strip()]
        if process.returncode == 0:
            log.info("Casos de recuperación (%s): %s", reason, lines[-1] if lines else "listo")
            bus.publish("recovery.updated", {"kind": "examples"})
        else:
            log.warning(
                "Casos de recuperación (%s) fallaron (código %s): %s",
                reason,
                process.returncode,
                " | ".join(lines[-5:]),
            )


# ------------------------------------------------------------------ simulaciones (rol admin)

REPLAY_SCRIPT = "replay_scenario.py"
SPEEDS = {"normal": 60.0, "rapida": 720.0}  # 1 h del evento = 1 min · todo en ~1 min


def _scripts_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[2] / "scripts", here.parents[4] / "scripts"):
        if (candidate / REPLAY_SCRIPT).exists():
            return candidate
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"detail": "No se encontró el script de reproducción", "code": "replay_missing"},
    )


class SimulationIn(BaseModel):
    mode: Literal["con_datos", "sin_datos"]
    speed: Literal["normal", "rapida"] = "rapida"
    rain: bool = Field(default=True, description="Curva de lluvia SIMULADA para la cascada")


class SimulationStatus(BaseModel):
    running: bool
    mode: Literal["con_datos", "sin_datos"] | None
    speed: Literal["normal", "rapida"] | None
    rain: bool
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    log_tail: list[str]


class _Simulation:
    def __init__(self) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self.mode: Literal["con_datos", "sin_datos"] | None = None
        self.speed: Literal["normal", "rapida"] | None = None
        self.rain = False
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.exit_code: int | None = None
        self.log: deque[str] = deque(maxlen=12)
        self.reader: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    def status(self) -> SimulationStatus:
        return SimulationStatus(
            running=self.running,
            mode=self.mode,
            speed=self.speed,
            rain=self.rain,
            started_at=self.started_at,
            finished_at=self.finished_at,
            exit_code=self.exit_code,
            log_tail=list(self.log),
        )

    async def _follow(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        async for raw in process.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                self.log.append(line)
        self.exit_code = await process.wait()
        self.finished_at = datetime.now(UTC)
        bus.publish("simulation.changed", {"running": False, "exit_code": self.exit_code})

    async def start_replay(self, speed: Literal["normal", "rapida"], rain: bool) -> None:
        settings = get_settings()
        scripts = _scripts_dir()
        args = [str(scripts / REPLAY_SCRIPT), "--reset", "--speed", str(SPEEDS[speed]), "--quiet"]
        if rain:
            args.append("--rain")
        env = {
            **os.environ,
            "API_BASE_URL": os.environ.get("API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
            "TOKEN_OPERADOR_PMU": settings.token_operador_pmu,
            "PYTHONUNBUFFERED": "1",
        }
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            *args,
            cwd=str(scripts),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self.reader = asyncio.create_task(self._follow(self.process))

    async def stop(self) -> None:
        if self.process is not None and self.running:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except TimeoutError:
                self.process.kill()
            self.log.append("Simulación detenida por el administrador.")


simulation = _Simulation()


@router.get("/simulation", response_model=SimulationStatus)
async def simulation_status(_: Role = Depends(require_role(Role.admin))) -> SimulationStatus:
    return simulation.status()


@router.post("/simulation", response_model=SimulationStatus, status_code=status.HTTP_202_ACCEPTED)
async def start_simulation(
    body: SimulationIn,
    _: Role = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
) -> SimulationStatus:
    """Con datos: reinicia y reproduce el escenario. Sin datos: deja la demo vacía."""
    _require_demo()
    await simulation.stop()
    simulation.log.clear()
    simulation.mode = body.mode
    simulation.started_at = datetime.now(UTC)
    simulation.finished_at = None
    simulation.exit_code = None
    if body.mode == "sin_datos":
        await _reset(session)
        simulation.speed = None
        simulation.rain = False
        simulation.finished_at = datetime.now(UTC)
        simulation.exit_code = 0
        simulation.log.append("Datos reiniciados: el tablero quedó vacío.")
    else:
        simulation.speed = body.speed
        simulation.rain = body.rain
        await simulation.start_replay(body.speed, body.rain)
    bus.publish("simulation.changed", {"running": simulation.running, "mode": body.mode})
    return simulation.status()


@router.post("/simulation/stop", response_model=SimulationStatus)
async def stop_simulation(_: Role = Depends(require_role(Role.admin))) -> SimulationStatus:
    await simulation.stop()
    return simulation.status()
