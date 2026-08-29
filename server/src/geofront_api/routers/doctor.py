from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
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

    Runs even with no open workspace — environment checks never require one,
    and the workspace probe reports a graceful "closed" status instead of 409.
    """
    state = get_state()
    environment = doctor_environment()

    if not state.is_open:
        return {
            "environment": environment,
            "workspace": {"ok": False, "closed": True, "checks": {"status": "no workspace open"}},
            "workspace_open": {"ok": False, "closed": True, "checks": {"open": False}},
        }

    ws = state.require_workspace()
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
    """Probe the configured LLM provider configuration (no secret values).

    Works without an open workspace by falling back to the gateway's default
    LLM health (env var + provider defaults).
    """
    state = get_state()
    if state.is_open:
        return doctor_llm_provider(state.require_workspace().settings)
    return state.llm_health()  # type: ignore[return-value]
