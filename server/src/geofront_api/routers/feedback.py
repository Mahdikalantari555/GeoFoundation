from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from geomemory import GeoMemory, GeoMemoryError
from geomemory.core.models import FeedbackEvent

from ..errors import GeoFrontError
from ..schemas import FeedbackRequest
from ..state import get_state

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=201)
async def record_feedback(req: FeedbackRequest) -> dict[str, object]:
    """Record an immutable feedback event (search hit thumbs, answer ratings)."""
    ws: GeoMemory = get_state().require_workspace()
    event = FeedbackEvent(
        target_type=req.target_type,
        target_id=req.target_id,
        label=req.label,
        actor=req.actor,
        payload=req.payload,
        metadata=req.metadata,
    )
    async with get_state().write_lock:
        try:
            stored = await run_in_threadpool(ws.record_feedback, event)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="feedback_failed", message=str(exc)) from exc
    return stored.model_dump(mode="json")


@router.get("/export")
async def export_feedback(task_type: str, output_dir: str | None = None) -> FileResponse:
    """Export accepted feedback examples for a task type as a downloadable JSONL."""
    ws = get_state().require_workspace()
    out = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out.mkdir(parents=True, exist_ok=True)
    async with get_state().write_lock:
        try:
            path = await run_in_threadpool(ws.export_dataset, task_type, out)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="feedback_export_failed", message=str(exc)) from exc
        except ValueError as exc:
            raise GeoFrontError(
                code="feedback_export_empty",
                message=str(exc),
                status_code=404,
            ) from exc
    return FileResponse(path, filename=path.name, media_type="application/jsonl")
