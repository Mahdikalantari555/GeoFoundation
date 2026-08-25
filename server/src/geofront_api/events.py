from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Bound queue size per subscriber — slow consumers drop events rather than
# block the loop; SSE clients recover by refetching on next event.
_SUBSCRIBER_QUEUE_SIZE = 256


class EventBus:
    """In-process pub/sub for SSE events.

    `publish` is safe to call from worker threads (ingest jobs) and from the
    event loop: delivery is scheduled onto the bound loop via
    `call_soon_threadsafe`.
    """

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running loop (called from app lifespan startup)."""
        self._loop = loop

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_SIZE)
        self._subs.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(queue)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        """Deliver `event` to all subscribers. Thread-safe; never raises."""
        loop = self._loop
        if loop is None:
            return  # no loop bound yet — nobody can be listening

        def _deliver() -> None:
            for queue in list(self._subs):
                try:
                    queue.put_nowait({"event": event, "data": data})
                except asyncio.QueueFull:
                    logger.warning("event_bus: subscriber dropped event %s", event)

        try:
            loop.call_soon_threadsafe(_deliver)
        except RuntimeError:
            logger.debug("event_bus: loop closed; event %s dropped", event)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_event_bus() -> None:
    global _bus
    _bus = EventBus()
