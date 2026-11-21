"""Exporta el contrato OpenAPI de FastAPI para generar los tipos del frontend (research R11).

Uso (desde la raíz del repo):
    uv run --project services/api python scripts/export_openapi.py
    cd apps/web && npm run gen:api
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.main import app  # noqa: E402

OUT = ROOT / "apps" / "web" / "lib" / "api" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI exportado → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
