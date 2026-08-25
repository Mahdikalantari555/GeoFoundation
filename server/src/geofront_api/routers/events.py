from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..events import get_event_bus

router = APIRouter(tags=["events"])

_KEEPALIVE_SECONDS = 15.0


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Server-sent events: `hello`, `job_progress`, `asset_created`,
    `collection_created`, `collection_archived`, `workspace_changed`.

    Clients refetch state on events; a `: ping` comment every 15s keeps the
    connection alive through proxies.
    """
    bus = get_event_bus()
    queue = await bus.subscribe()

    async def stream() -> AsyncIterator[str]:
        try:
            yield _sse("hello", {"message": "connected"})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield _sse(record["event"], record["data"])
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
