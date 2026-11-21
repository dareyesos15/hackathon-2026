"""Bus de eventos en memoria (research R5). Interfaz `EventBus` para cambiar a Kafka después.

Un solo worker de Uvicorn: los suscriptores son colas asyncio en el mismo proceso.
"""

import asyncio
import itertools
import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    id: int
    type: str
    data: dict[str, Any]

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False, default=str)
        return f"id: {self.id}\nevent: {self.type}\ndata: {payload}\n\n"


class EventBus(Protocol):
    def publish(self, type_: str, data: dict[str, Any]) -> Event: ...

    def subscribe(self, last_event_id: int | None = None) -> "asyncio.Queue[Event]": ...

    def unsubscribe(self, queue: "asyncio.Queue[Event]") -> None: ...


class InMemoryEventBus:
    """Difunde eventos a todos los suscriptores y guarda los últimos `buffer_size`."""

    def __init__(self, buffer_size: int = 500, queue_size: int = 1000) -> None:
        self._ids = itertools.count(1)
        self._buffer: deque[Event] = deque(maxlen=buffer_size)
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._queue_size = queue_size

    def publish(self, type_: str, data: dict[str, Any]) -> Event:
        event = Event(id=next(self._ids), type=type_, data=data)
        self._buffer.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Cliente lento: se descarta; reconectará con Last-Event-ID o caerá a polling.
                self._subscribers.discard(queue)
        return event

    def subscribe(self, last_event_id: int | None = None) -> "asyncio.Queue[Event]":
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        if last_event_id is not None:
            for event in self._buffer:
                if event.id > last_event_id:
                    queue.put_nowait(event)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[Event]") -> None:
        self._subscribers.discard(queue)


bus = InMemoryEventBus()
