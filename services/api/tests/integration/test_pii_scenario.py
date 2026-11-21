"""Ningún teléfono, cédula o correo del escenario llega a la base (SC-004, CLAUDE.md §14)."""

import json
import re

import httpx
from sqlalchemy import text

from app.config import get_settings
from app.core.privacy import contains_pii
from app.db import SessionLocal
from tests.integration.conftest import PMU


async def test_full_scenario_stores_no_personal_data(client: httpx.AsyncClient) -> None:
    lines = [
        json.loads(line)
        for line in (get_settings().data_dir / "seed" / "scenario.jsonl").read_text().splitlines()
        if line.strip()
    ]
    contacts: set[str] = set()
    for line in lines:
        body = line["body"]
        contact = body.get("reporter_contact") or body.get("from")
        if contact:
            contacts.add(re.sub(r"\D", "", contact)[-10:])
        resp = await client.post(line["endpoint"], json=body, headers=PMU)
        assert resp.status_code in (200, 201), resp.text

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT text_redacted, coalesce(location_text, '') FROM reports")
            )
        ).all()
        dump = (
            await session.execute(text("SELECT string_agg(r::text, ' ') FROM reports r"))
        ).scalar_one()
        events = (
            await session.execute(text("SELECT string_agg(payload::text, ' ') FROM report_events"))
        ).scalar_one()

    assert len(rows) >= len(lines)
    leaks = [t for row in rows for t in row if contains_pii(t)]
    assert not leaks, leaks[:5]
    for phone in contacts:
        assert phone not in dump, "un teléfono de remitente quedó en la tabla reports"
        assert phone not in (events or ""), "un teléfono quedó en la bitácora"
