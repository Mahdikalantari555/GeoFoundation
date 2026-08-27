from __future__ import annotations

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


def _require_or_409() -> GeoMemory:
    return get_state().require_workspace()


def _settings_dict(ws: GeoMemory) -> dict[str, object]:
    return cast(dict[str, object], ws.settings.model_dump(mode="json"))


def _settings_response(settings: Any) -> dict[str, object]:
    return cast(dict[str, object], settings.model_dump(mode="json"))


@router.post("/create", status_code=201)
async def create_workspace(req: CreateWorkspaceRequest) -> dict[str, object]:
    state = get_state()
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
            ws = await run_in_threadpool(GeoMemory.create, req.path, config)
        except WorkspaceExistsError as exc:
            raise GeoFrontError(
                code="workspace_exists",
                message=f"Workspace already exists at {req.path}. Use open instead.",
                status_code=409,
            ) from exc
        except GeoMemoryError as exc:
            raise GeoFrontError(
                code="workspace_create_failed", message=str(exc), status_code=400
            ) from exc
        state.workspace = ws
        state.workspace_path = ws.path
        get_agent_service().init(state.workspace_path)
    get_event_bus().publish(
        "workspace_changed", {"status": "open", "path": str(state.workspace_path)}
    )
    return {"status": "open", "path": str(state.workspace_path), "settings": _settings_dict(ws)}


@router.post("/open")
async def open_workspace(req: OpenWorkspaceRequest) -> dict[str, object]:
    state = get_state()
    async with state.write_lock:
        await state._close_locked()
        try:
            ws = await run_in_threadpool(GeoMemory.open, req.path)
        except WorkspaceNotFoundError as exc:
            raise GeoFrontError(
                code="workspace_not_found",
                message=f"No workspace found at {req.path}.",
                status_code=404,
            ) from exc
        except GeoMemoryError as exc:
            raise GeoFrontError(
                code="workspace_open_failed", message=str(exc), status_code=400
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
    changes = req.model_dump(exclude_unset=True, exclude_none=True)
    async with get_state().write_lock:
        try:
            updated = await run_in_threadpool(ws.update_settings, **changes)
        except ValueError as exc:
            raise GeoFrontError(
                code="invalid_setting", message=str(exc), status_code=422
            ) from exc
    return _settings_response(updated)
