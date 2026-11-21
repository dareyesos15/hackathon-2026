"""El motor nunca ve la verdad del escenario (principio IV, research R8)."""

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "app" / "core"
FORBIDDEN_MODULES = ("app.routers.metrics", "metrics")
FORBIDDEN_TEXT = ("ground_truth",)


def test_core_does_not_import_metrics_or_ground_truth() -> None:
    offenders: list[str] = []
    for path in CORE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == m or name.endswith("." + m) for m in FORBIDDEN_MODULES):
                    offenders.append(f"{path.name}: import {name}")
        for word in FORBIDDEN_TEXT:
            if word in source:
                offenders.append(f"{path.name}: menciona {word}")
    assert not offenders, offenders
