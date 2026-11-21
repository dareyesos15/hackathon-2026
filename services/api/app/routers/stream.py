"""Eventos en vivo para el tablero: GET /stream (SSE; contracts/sse-events.md).

Única excepción al REST puro (principio X). Si falla, el cliente cae a polling REST.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.adapters.event_bus import bus
from app.auth import require_role
from app.domain import Role

router = APIRouter(tags=["tiempo real"])
HEARTBEAT_SECONDS = 15.0


@router.get(
    "/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Server-Sent Events"}},
)
async def stream(
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    _: Role = Depends(require_role(Role.operador_pmu, allow_query_token=True)),
) -> StreamingResponse:
    last_id = int(last_event_id) if last_event_id and last_event_id.isdigit() else None
    queue = bus.subscribe(last_id)

    async def events() -> AsyncIterator[str]:
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield event.to_sse()
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
