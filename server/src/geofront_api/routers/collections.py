from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import CollectionNotFoundError, GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..schemas import CreateCollectionRequest
from ..state import get_state

router = APIRouter(prefix="/collections", tags=["collections"])


def _require_ws() -> GeoMemory:
    return get_state().require_workspace()


def _not_found(collection_id: str) -> GeoFrontError:
    return GeoFrontError(
        code="collection_not_found",
        message=f"Collection not found: {collection_id}",
        status_code=404,
    )


@router.get("")
async def list_collections() -> list[dict[str, object]]:
    ws = _require_ws()
    cols = await run_in_threadpool(ws.list_collections)
    return [c.model_dump(mode="json") for c in cols]


@router.post("", status_code=201)
async def create_collection(req: CreateCollectionRequest) -> dict[str, object]:
    ws = _require_ws()
    try:
        col = await run_in_threadpool(
            ws.create_collection, req.name, req.description or ""
        )
    except GeoMemoryError as exc:
        raise GeoFrontError(code="collection_create_failed", message=str(exc)) from exc
    return col.model_dump(mode="json")


@router.get("/{collection_id}")
async def get_collection(collection_id: str) -> dict[str, object]:
    ws = _require_ws()
    col = await run_in_threadpool(ws.get_collection, collection_id)
    if col is None:
        raise _not_found(collection_id)
    return col.model_dump(mode="json")


@router.delete("/{collection_id}")
async def archive_collection(collection_id: str) -> dict[str, object]:
    ws = _require_ws()
    try:
        archived = await run_in_threadpool(ws.archive_collection, collection_id)
    except CollectionNotFoundError as exc:
        raise _not_found(collection_id) from exc
    if not archived:
        raise _not_found(collection_id)
    return {"archived": True, "id": collection_id}
