from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..filters import build_spatial_filter, build_temporal_filter
from ..schemas import SearchRequest
from ..state import get_state

router = APIRouter(tags=["search"])


def _require_ws() -> GeoMemory:
    return get_state().require_workspace()


@router.post("/search")
async def search(req: SearchRequest) -> dict[str, object]:
    """Hybrid (sparse/dense/hybrid) retrieval with optional filters.

    Search persists a retrieval run, so it runs behind the platform write lock.
    """
    ws = _require_ws()
    spatial = build_spatial_filter(req.spatial)
    temporal = build_temporal_filter(req.temporal)
    async with get_state().write_lock:
        try:
            result = await run_in_threadpool(
                ws.search,
                req.query,
                mode=req.mode,
                top_k=req.top_k,
                top_n=req.top_n,
                collections=req.collections,
                spatial=spatial,
                temporal=temporal,
                sensor=req.sensor,
            )
        except GeoMemoryError as exc:
            raise GeoFrontError(code="search_failed", message=str(exc)) from exc
    return result.model_dump(mode="json")
