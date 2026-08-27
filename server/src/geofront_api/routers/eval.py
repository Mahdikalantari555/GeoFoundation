from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError

from ..errors import GeoFrontError
from ..schemas import RunEvalRequest
from ..state import get_state

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run")
async def run_eval(req: RunEvalRequest) -> dict[str, object]:
    """Run a benchmark (JSONL) against the active workspace."""
    ws: GeoMemory = get_state().require_workspace()
    async with get_state().write_lock:
        try:
            result = await run_in_threadpool(ws.run_benchmark, req.benchmark_path, req.config)
        except FileNotFoundError as exc:
            raise GeoFrontError(
                code="eval_file_not_found", message=str(exc), status_code=404
            ) from exc
        except GeoMemoryError as exc:
            raise GeoFrontError(code="eval_failed", message=str(exc)) from exc
    return result.model_dump(mode="json")
