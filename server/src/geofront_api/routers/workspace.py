from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory, GeoMemoryError, WorkspaceNotFoundError
from geomemory.core.exceptions import WorkspaceExistsError
from geomemory.core.models import WorkspaceConfig

from ..errors import GeoFrontError
from ..events import get_event_bus
from ..schemas import (
    CreateWorkspaceRequest,
    OpenWorkspaceRequest,
    UpdateSettingsRequest,
)
from ..services.agent import get_agent_service, reset_agent_service
from ..state import get_state

router = APIRouter(prefix="/workspace", tags=["workspace"])
log = logging.getLogger("geofront.workspace")


def _open_workspace_path(raw_path: str) -> GeoMemory:
    """Open the workspace at ``raw_path``.

    Workspaces are stored nested under ``path/<name>/`` (see create). If the
    given path is not itself a workspace but contains exactly one workspace
    subdirectory, open that — so a user can pass the parent directory.
    """
    try:
        return GeoMemory.open(raw_path)
    except WorkspaceNotFoundError:
        parent = Path(raw_path).expanduser()
        if not parent.is_dir():
            raise
        for child in sorted(parent.iterdir()):
            if child.is_dir():
                try:
                    return GeoMemory.open(child)
                except WorkspaceNotFoundError:
                    continue
        raise


def _require_or_409() -> GeoMemory:
    return get_state().require_workspace()


def _settings_dict(ws: GeoMemory) -> dict[str, object]:
    return cast(dict[str, object], ws.settings.model_dump(mode="json"))


def _settings_response(settings: Any) -> dict[str, object]:
    return cast(dict[str, object], settings.model_dump(mode="json"))


@router.post("/create", status_code=201)
async def create_workspace(req: CreateWorkspaceRequest) -> dict[str, object]:
    state = get_state()
    # Files must live in path/workspacename/ — enforce nested mkdir per spec
    base = Path(req.path).expanduser()
    # sanitize workspace name for filesystem (allow letters, digits, - _)
    safe_name = req.name.strip() or "GeoMemory Workspace"
    target = base / safe_name if base.name != safe_name else base
    target.mkdir(parents=True, exist_ok=True)
    full_path = str(target.resolve())
    log.info("create workspace: target=%s name=%s base=%s", full_path, req.name, req.path)
    async with state.write_lock:
        await state._close_locked()
        config = WorkspaceConfig(
            name=req.name,
            language=req.language,  # type: ignore[arg-type]
            offline=req.offline,
            model_path=req.model_path,
            embedding_path=req.embedding_path,
            vision_path=req.vision_path,
            default_collection=req.default_collection,
        )
        try:
            ws = await run_in_threadpool(GeoMemory.create, full_path, config)
        except WorkspaceExistsError as exc:
            raise GeoFrontError(
                code="workspace_exists",
                message=f"Workspace already exists at {full_path}. Use open instead.",
                status_code=409,
            ) from exc
        except GeoMemoryError as exc:
            raise GeoFrontError(
                code="workspace_create_failed", message=str(exc), status_code=400
            ) from exc
        state.workspace = ws
        state.workspace_path = ws.path
        # Seed LLM connection from gateway env when not specified by the request —
        # lets a deployed server apply GEOMEMORY_LLM_API_BASE_URL / _MODEL_ID.
        env_overrides = {
            k: os.environ[k]
            for k in ("GEOMEMORY_LLM_API_BASE_URL", "GEOMEMORY_LLM_MODEL_ID")
            if os.environ.get(k)
        }
        if env_overrides:
            mapped = {
                "llm_api_base_url": env_overrides.get("GEOMEMORY_LLM_API_BASE_URL"),
                "llm_model_id": env_overrides.get("GEOMEMORY_LLM_MODEL_ID"),
            }
            try:
                ws.update_settings(**{k: v for k, v in mapped.items() if v is not None})
            except ValueError as exc:
                log.warning("could not apply env LLM defaults: %s", exc)
        get_agent_service().init(state.workspace_path)
    get_event_bus().publish(
        "workspace_changed", {"status": "open", "path": str(state.workspace_path)}
    )
    return {"status": "open", "path": str(state.workspace_path), "settings": _settings_dict(ws)}


@router.post("/open")
async def open_workspace(req: OpenWorkspaceRequest) -> dict[str, object]:
    log.info("open workspace: path=%s", req.path)
    state = get_state()
    async with state.write_lock:
        await state._close_locked()
        try:
            ws = await run_in_threadpool(_open_workspace_path, req.path)
        except WorkspaceNotFoundError as exc:
            raise GeoFrontError(
                code="workspace_not_found",
                message=f"No workspace found at {req.path}.",
                status_code=404,
            ) from exc
        state.workspace = ws
        state.workspace_path = ws.path
        get_agent_service().init(state.workspace_path)
    get_event_bus().publish(
        "workspace_changed", {"status": "open", "path": str(state.workspace_path)}
    )
    return {"status": "open", "path": str(state.workspace_path), "settings": _settings_dict(ws)}


@router.post("/close")
async def close_workspace() -> dict[str, object]:
    state = get_state()
    await state.close()
    reset_agent_service()
    get_event_bus().publish("workspace_changed", {"status": "closed", "path": None})
    return {"status": "closed"}


@router.get("")
async def get_workspace() -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        return {"status": "closed", "path": None, "settings": None}
    return {
        "status": "open",
        "path": str(state.workspace_path),
        "settings": _settings_dict(state.require_workspace()),
    }


@router.get("/stats")
async def workspace_stats() -> dict[str, object]:
    ws = _require_or_409()
    async with get_state().write_lock:
        return await run_in_threadpool(ws.stats)


@router.put("/settings")
async def update_settings(req: UpdateSettingsRequest) -> dict[str, object]:
    ws = _require_or_409()
    # API key must never be set through settings — server env only (AGENTS.md invariant #3)
    if "llm_api_key_env" in req.model_fields_set:
        raise GeoFrontError(
            code="setting_forbidden",
            message=(
                "The LLM API key is read from the server environment only. "
                "Set the env var named by llm_api_key_env on the server; do not "
                "send a key through this API."
            ),
            status_code=422,
        )
    changes = req.model_dump(exclude_unset=True, exclude_none=True)
    async with get_state().write_lock:
        try:
            updated = await run_in_threadpool(ws.update_settings, **changes)
        except ValueError as exc:
            raise GeoFrontError(
                code="invalid_setting", message=str(exc), status_code=422
            ) from exc
    return _settings_response(updated)
