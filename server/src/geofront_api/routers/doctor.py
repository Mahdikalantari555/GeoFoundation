from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory
from geomemory.services.doctor import (
    doctor_environment,
    doctor_llm_provider,
    doctor_workspace,
)

from ..state import get_state

router = APIRouter(prefix="/doctor", tags=["doctor"])


@router.get("")
async def doctor() -> dict[str, object]:
    """Environment + active-workspace diagnostics (no secret values).

    Probes the already-open workspace instead of reopening it (reopening the
    same SQLite database while it is live can deadlock).
    """
    ws: GeoMemory = get_state().require_workspace()
    environment = doctor_environment()
    workspace_report = doctor_workspace(ws.path)

    try:
        await run_in_threadpool(ws.list_collections)
        collections_ok = True
        collections_err: str | None = None
    except Exception as exc:  # noqa: BLE001 - report failure
        collections_ok = False
        collections_err = str(exc)

    try:
        await run_in_threadpool(ws.stats)
        stats_ok = True
    except Exception:  # noqa: BLE001 - report failure
        stats_ok = False

    workspace_open = {
        "ok": collections_ok and stats_ok,
        "checks": {
            "open_list_collections": collections_ok,
            "stats": stats_ok,
        },
    }
    if collections_err is not None:
        workspace_open["checks"]["open_error"] = collections_err

    return {
        "environment": environment,
        "workspace": workspace_report,
        "workspace_open": workspace_open,
    }


@router.get("/llm")
async def doctor_llm() -> dict[str, object]:
    """Probe the configured LLM provider configuration (no secret values)."""
    ws = get_state().require_workspace()
    return doctor_llm_provider(ws.settings)
