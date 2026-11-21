"""Fuentes públicas: filtro de contratos del sismo y verificación de las copias fechadas."""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.public_sources import (
    SECOP_FIELDS,
    Snapshot,
    digest,
    is_earthquake_contract,
    load_snapshot,
)


def test_contract_filter_keeps_earthquake_objects_only() -> None:
    assert is_earthquake_contract("Obras para conjurar la situación de CALAMIDAD pública")
    assert is_earthquake_contract("Gerencia de la reconstrucción con ocasión del sismo")
    assert is_earthquake_contract("Subsidios de arrendamiento temporal para damnificados")
    assert is_earthquake_contract("Diseño sismorresistente del colegio")
    assert not is_earthquake_contract("Mantenimiento de plantas de emergencia y extintores")
    assert not is_earthquake_contract("Retiro de derrumbes y escombros en vías")
    assert not is_earthquake_contract("Mecanismo de seguimiento del turismo")


def test_secop_snapshot_never_keeps_personal_fields() -> None:
    personal = {"documento_proveedor", "proveedor_adjudicado", "nombre_representante_legal"}
    assert personal.isdisjoint(SECOP_FIELDS)


def _write(tmp: Path, records: list[dict], sha: str | None = None) -> None:
    snap = Snapshot(
        name="prueba",
        title="Prueba",
        source="Fuente",
        query_url="https://example.org/q",
        license="CC BY-SA 4.0",
        attribution="Autor",
        fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
        records=records,
        sha256=digest(records),
    )
    data = snap.to_json()
    if sha:
        data["sha256"] = sha
    (tmp / "prueba.json").write_text(json.dumps(data), encoding="utf-8")


def test_snapshot_round_trip_is_verified(tmp_path: Path) -> None:
    _write(tmp_path, [{"id": 1, "valor": 10.0}])
    snap = load_snapshot("prueba", tmp_path)
    assert snap is not None and snap.verified
    assert snap.records == [{"id": 1, "valor": 10.0}]


def test_tampered_snapshot_is_flagged(tmp_path: Path) -> None:
    _write(tmp_path, [{"id": 1}], sha="0" * 64)
    snap = load_snapshot("prueba", tmp_path)
    assert snap is not None and not snap.verified


def test_missing_snapshot_returns_none(tmp_path: Path) -> None:
    assert load_snapshot("no_existe", tmp_path) is None
