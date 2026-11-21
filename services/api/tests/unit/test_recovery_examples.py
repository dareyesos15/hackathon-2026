"""La carga automática de los casos de ejemplo solo corre si está activada en modo demo."""

import asyncio

from app.config import get_settings
from app.routers import demo


def test_examples_are_off_by_default() -> None:
    assert get_settings().seed_recovery_examples is False


def test_schedule_does_nothing_when_disabled() -> None:
    async def run() -> int:
        demo.schedule_recovery_examples("prueba")
        return len(demo._seed_tasks)

    assert asyncio.run(run()) == 0


def test_seed_script_ships_next_to_the_replay() -> None:
    assert (demo._scripts_dir() / demo.SEED_SCRIPT).exists()
