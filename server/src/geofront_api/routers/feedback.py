from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
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
