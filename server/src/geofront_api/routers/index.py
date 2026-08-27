from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..state import get_state

router = APIRouter(prefix="/index", tags=["index"])


@router.post("/build")
async def build_index(space_id: str = "text.nomic.v1") -> dict[str, object]:
    """Build the retrieval index for a space from stored embeddings."""
    ws: GeoMemory = get_state().require_workspace()
    async with get_state().write_lock:
        try:
            await run_in_threadpool(ws.build_index, space_id)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="index_build_failed", message=str(exc)) from exc
    return {"status": "built", "space_id": space_id}


@router.post("/rebuild")
async def rebuild_index(space_id: str = "text.nomic.v1") -> dict[str, object]:
    """Rebuild the index for a space from the SQLite source of truth."""
    ws = get_state().require_workspace()
    async with get_state().write_lock:
        try:
            await run_in_threadpool(ws.rebuild_index, space_id)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="index_rebuild_failed", message=str(exc)) from exc
    return {"status": "rebuilt", "space_id": space_id}
