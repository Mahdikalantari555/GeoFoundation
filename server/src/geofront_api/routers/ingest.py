from __future__ import annotations

import base64
import binascii
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from geomemory import AssetNotFoundError, GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import IngestBytesRequest
from ..state import get_state

router = APIRouter(tags=["ingest"])

# Matches geomemory's loader table (DOCX is a known gap — not accepted here).
ACCEPTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".pdf",
    ".py",
    ".js",
    ".ipynb",
    ".geojson",
    ".gpkg",
    ".tif",
    ".tiff",
}


def _require_ws() -> GeoMemory:
    return get_state().require_workspace()


def _check_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_EXTENSIONS:
        raise GeoFrontError(
            code="unsupported_format",
            message=f"Unsupported file type: '{suffix or filename}'. "
            f"Accepted: {', '.join(sorted(ACCEPTED_EXTENSIONS))}",
            status_code=422,
        )


def _make_ingest_job(
    ws: GeoMemory,
    filename: str,
    data: bytes,
    collection_id: str,
    parser: str | None,
    index_after: bool,
) -> Callable[[], dict[str, object]]:
    """Build a job closure that owns its temp file lifecycle."""

    def _run() -> dict[str, object]:
        with tempfile.TemporaryDirectory(prefix="gf-ingest-") as tmp:
            target = Path(tmp) / filename
            target.write_bytes(data)
            job = ws.ingest(target, collection_id, parser=parser, index_after=index_after)
            payload: dict[str, object] = dict(job.result or {})
            payload["job_type"] = job.type
            if job.error is not None:
                payload["error"] = job.error
            asset_id = payload.get("asset_id")
            if asset_id and not payload.get("skipped"):
                # Thread context — EventBus.publish is thread-safe.
                from ..events import get_event_bus

                get_event_bus().publish(
                    "asset_created",
                    {"asset_id": asset_id, "collection_id": collection_id, "filename": filename},
                )
            return payload

    return _run


async def _submit(ws: GeoMemory, filename: str, data: bytes, collection_id: str,
                  parser: str | None, index_after: bool) -> dict[str, str]:
    record = await get_job_manager().submit(
        "ingestion", _make_ingest_job(ws, filename, data, collection_id, parser, index_after)
    )
    return {"job_id": record.id, "status": "accepted"}


@router.post("/ingest", status_code=202)
async def ingest_file(
    file: Annotated[UploadFile, File()],
    collection_id: Annotated[str, Form()],
    index_after: Annotated[bool, Form()] = True,
    parser: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    ws = _require_ws()
    _check_extension(file.filename or "")
    data = await file.read()
    return await _submit(ws, file.filename or "upload", data, collection_id, parser, index_after)


@router.post("/ingest/bytes", status_code=202)
async def ingest_bytes(req: IngestBytesRequest) -> dict[str, str]:
    ws = _require_ws()
    _check_extension(req.filename)
    try:
        raw = base64.b64decode(req.data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GeoFrontError(
            code="invalid_base64", message="data_base64 is not valid base64.", status_code=422
        ) from exc
    return await _submit(ws, req.filename, raw, req.collection_id, req.parser, req.index_after)


@router.get("/assets")
async def list_assets(collection_id: str | None = None) -> list[dict[str, object]]:
    ws = _require_ws()
    assets = await run_in_threadpool(ws.list_assets, collection_id)
    return [a.model_dump(mode="json") for a in assets]


@router.get("/assets/{asset_id}")
async def inspect_asset(asset_id: str) -> dict[str, object]:
    ws = _require_ws()
    try:
        detail = await run_in_threadpool(ws.inspect, asset_id)
    except AssetNotFoundError as exc:
        raise GeoFrontError(
            code="asset_not_found",
            message=f"Asset not found: {asset_id}",
            status_code=404,
        ) from exc
    except GeoMemoryError as exc:
        raise GeoFrontError(code="inspect_failed", message=str(exc), status_code=400) from exc
    return detail.model_dump(mode="json")
