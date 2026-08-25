from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemoryError

from ..errors import GeoFrontError
from ..filters import build_search_filters
from ..schemas import AskRequest
from ..state import get_state

router = APIRouter(tags=["ask"])


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
                ws.ask, req.question, mode=req.mode, collections=req.collections,
                filters=filters,
            )
        except GeoMemoryError as exc:
            raise GeoFrontError(code="ask_failed", message=str(exc)) from exc
    return result.model_dump(mode="json")
