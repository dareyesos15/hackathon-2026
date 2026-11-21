"""El contrato que consume el frontend coincide con el OpenAPI actual (principio X, research R11).

Si falla: `uv run --project services/api python scripts/export_openapi.py` y
`cd apps/web && npm run gen:api`, en el mismo commit que cambió los esquemas.
"""

import json
from pathlib import Path

import pytest

from app.main import app

SNAPSHOT = Path(__file__).resolve().parents[4] / "apps" / "web" / "lib" / "api" / "openapi.json"


def test_frontend_contract_is_up_to_date() -> None:
    if not SNAPSHOT.exists():
        pytest.skip("El frontend no está disponible en este entorno (p. ej. dentro del contenedor)")
    current = json.loads(json.dumps(app.openapi(), sort_keys=True))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == snapshot, "OpenAPI desalineado: regenere openapi.json y schema.d.ts"


def test_all_routes_are_versioned() -> None:
    paths = app.openapi()["paths"]
    assert paths
    assert all(p.startswith("/api/v1/") for p in paths), list(paths)
