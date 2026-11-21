"""Configuración global de pruebas.

Las pruebas de integración usan una base aparte (`<db>_test`) para no tocar los datos de la demo.
Se define antes de que cualquier módulo cree el engine de SQLAlchemy.
"""

import os

_base = os.environ.get("DATABASE_URL", "postgresql+asyncpg://dacora:dacora@localhost:5432/dacora")
if not _base.rstrip("/").endswith("_test"):
    head, _, name = _base.rpartition("/")
    os.environ["DATABASE_URL"] = f"{head}/{name}_test"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()
