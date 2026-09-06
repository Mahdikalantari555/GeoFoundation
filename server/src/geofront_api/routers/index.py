from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..state import get_state

router = APIRouter(prefix="/index", tags=["index"])
log = logging.getLogger("geofront.index")


def _auto_download_fallback(ws: GeoMemory) -> None:
    """Attempt inline download when no local model and offline is False.

    Raises ``GeoFrontError`` 503 when offline or download fails.
    """
    settings = ws.settings
    backend = settings.embedding_backend
    if backend not in ("sentence-transformers", "onnx"):
        return
    model_name = settings.onnx_model_name if backend == "onnx" else settings.st_model_name
    from geomemory.embeddings.hub import EmbeddingModelHub

    hub = EmbeddingModelHub()
    tag = "onnx" if backend == "onnx" else "st"
    if hub.find_model(model_name, backend=tag) is not None:
        return
    if settings.offline:
        raise GeoFrontError(
            code="embedding_unavailable",
            message=f"Model '{model_name}' is not cached locally and workspace is offline.",
            status_code=503,
            detail={"offline": True, "hint": "set offline=false or pre-download"},
        )
    try:
        hub.download(model_name, backend=tag)
    except Exception as exc:
        raise GeoFrontError(
            code="embedding_download_failed",
            message=f"Failed to auto-download model '{model_name}': {exc}",
            status_code=503,
            detail={"offline": settings.offline, "hint": "set offline=false or pre-download"},
        ) from exc


@router.post("/build")
async def build_index(space_id: str = "text.nomic.v1") -> dict[str, object]:
    """Build the retrieval index for a space from stored embeddings."""
    ws: GeoMemory = get_state().require_workspace()
    async with get_state().write_lock:
        try:
            await run_in_threadpool(_auto_download_fallback, ws)
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
            await run_in_threadpool(_auto_download_fallback, ws)
            await run_in_threadpool(ws.rebuild_index, space_id)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="index_rebuild_failed", message=str(exc)) from exc
    return {"status": "rebuilt", "space_id": space_id}
