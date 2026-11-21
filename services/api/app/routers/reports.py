"""Consulta de reportes: GET /reports (contracts/rest-api.md)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_role
from app.db import get_session
from app.domain import Category, ReportStatus, Role, TriageLevel
from app.models import Report
from app.schemas import ReportList
from app.serializers import reports_out

router = APIRouter(prefix="/reports", tags=["reportes"])


@router.get("", response_model=ReportList)
async def list_reports(
    status: ReportStatus | None = None,
    triage: TriageLevel | None = None,
    category: Category | None = None,
    incident_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = None,
    _: Role = Depends(require_role(Role.operador_pmu, Role.coe)),
    session: AsyncSession = Depends(get_session),
) -> ReportList:
    stmt = select(Report)
    if status:
        stmt = stmt.where(Report.status == status)
    if triage:
        stmt = stmt.where(Report.triage_level == triage)
    if category:
        stmt = stmt.where(Report.category == category)
    if incident_id:
        stmt = stmt.where(Report.incident_id == incident_id)
    if since:
        stmt = stmt.where(Report.received_at >= since)
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    rows = list(
        (
            await session.execute(
                stmt.order_by(Report.received_at, Report.id).offset(offset).limit(limit + 1)
            )
        ).scalars()
    )
    next_cursor = str(offset + limit) if len(rows) > limit else None
    return ReportList(
        items=await reports_out(session, rows[:limit]),
        next_cursor=next_cursor,
        cutoff_at=datetime.now(UTC),
    )
