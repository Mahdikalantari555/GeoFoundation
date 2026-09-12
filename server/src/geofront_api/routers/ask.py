from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemoryError
from pydantic import BaseModel, Field

from ..errors import GeoFrontError
from ..filters import build_search_filters
from ..schemas import AskRequest
from ..state import get_state

router = APIRouter(tags=["ask"])


class SuggestRequest(BaseModel):
    model_config = {"extra": "forbid"}

    content: str = Field(min_length=1, max_length=10000)
    memory_type: str | None = Field(default=None, description="Override memory type; defaults to 'correction'")


@router.post("/ask")
async def ask(req: AskRequest) -> dict[str, object]:
    """Grounded QA: retrieve → answer with citations, or abstain.

    Abstention is a normal 200 outcome (`abstained: true` + reason), never an
    error. The lib persists runs/answers/citations, so the call runs behind
    the platform write lock.
    """
    ws = get_state().require_workspace()
    filters = build_search_filters(
        req.spatial,
        req.temporal,
        collections=req.collections,
        sensors=req.sensor,
    )
    async with get_state().write_lock:
        try:
            result = await run_in_threadpool(
                ws.ask,
                req.question,
                mode=req.mode,
                collections=req.collections,
                filters=filters,
                modalities=req.modalities,
                modality_weight=req.modality_weight,
            )
        except GeoMemoryError as exc:
            raise GeoFrontError(code="ask_failed", message=str(exc)) from exc
    return result.model_dump(mode="json")


@router.post("/ask/{turn_id}/suggest", status_code=201)
async def suggest_correction(turn_id: str, req: SuggestRequest) -> dict[str, object]:
    """Create a CandidateMemory from a user-supplied correction on an answered turn."""
    ws = get_state().require_workspace()

    def _suggest() -> dict[str, object]:
        from geomemory.services.candidate_memory_service import CandidateMemoryService
        from geomemory.storage.repositories.conversation_repo import TurnRepository

        turn_repo = TurnRepository(ws.conn)
        turn = turn_repo.get(turn_id)
        if turn is None:
            raise GeoFrontError(code="turn_not_found", message=f"Turn {turn_id} not found", status_code=404)

        memory_type = req.memory_type or "correction"
        svc = CandidateMemoryService(ws.conn)
        cm = svc.create(
            content=req.content,
            memory_type=memory_type,
            source_feedback_ids=[turn_id],
            author=None,
        )
        svc.score(cm.id, {"confirming": 0})  # ensures state is set from default base score
        updated = svc.get(cm.id) or cm
        return updated.model_dump(mode="json")

    async with get_state().write_lock:
        return await run_in_threadpool(_suggest)

