"""Agent chat route: SSE streaming chat with the GeoAgent core."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent", tags=["agent"])

_KEEPALIVE_SECONDS = 15.0


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.post("/chat")
async def chat(req: Request, body: ChatRequest) -> StreamingResponse:
    """Stream agent chat responses via SSE.

    Events: `conversation`, `thinking`, `tool_start`, `tool_end`,
    `message`, `error`, `done`.
    """
    service = get_agent_service()
    if not service.is_initialized:
        raise GeoFrontError(
            code="agent_not_ready",
            message="Agent not initialized. Open a workspace first.",
            status_code=409,
        )

    core = service.core
    conv_id = body.conversation_id or core.new_conversation("web-chat")

    async def stream() -> AsyncIterator[str]:
        yield _sse("conversation", {"conversation_id": conv_id})
        yield _sse("thinking", {})

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_event(text: str) -> None:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, text)
            except RuntimeError:
                pass

        def run_chat() -> str:
            return core.chat(conv_id, body.message, on_event=on_event)

        task = asyncio.create_task(asyncio.to_thread(run_chat))

        try:
            while not task.done():
                try:
                    event_text = await asyncio.wait_for(
                        queue.get(), timeout=_KEEPALIVE_SECONDS
                    )
                    if event_text is None:
                        break
                    if event_text.startswith("[tool]"):
                        parts = event_text.split(" -> ", 1)
                        tool_name = parts[0].replace("[tool] ", "").strip()
                        status_info = parts[1].len(parts) > 1 and parts[1] or ""
                        yield _sse("tool_start", {"tool": tool_name})
                        yield _sse("tool_end", {"tool": tool_name, "status": status_info})
                    else:
                        yield _sse("message", {"text": event_text})
                except asyncio.TimeoutError:
                    yield ": ping\n\n"

            answer = await task
            yield _sse("message", {"text": answer, "final": True})
            yield _sse("done", {"conversation_id": conv_id})
        except Exception as exc:  # noqa: BLE001 - SSE error path
            yield _sse("error", {"message": str(exc)})
            yield _sse("done", {"conversation_id": conv_id})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _error_stream(code: str, message: str) -> AsyncIterator[str]:
    yield _sse("error", {"code": code, "message": message})
    yield _sse("done", {})
