"""Agent tools route: list registered tools and call them directly."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/tools", tags=["agent"])


@router.get("")
async def list_tools() -> dict[str, object]:
    """List all registered agent tools with their definitions."""
    service = get_agent_service()
    registry = service.registry

    tools = []
    for name in registry.names():
        tool_def = registry.get(name)
        if tool_def:
            tools.append({
                "name": tool_def.name,
                "description": tool_def.description,
                "params": tool_def.params,
                "returns": tool_def.returns,
                "timeout_s": tool_def.timeout_s,
                "cacheable": tool_def.cacheable,
            })

    return {"tools": tools}


class ToolCallRequest(BaseModel):
    args: dict[str, Any] = {}


@router.post("/{tool_name}/call")
async def call_tool(tool_name: str, body: ToolCallRequest) -> dict[str, object]:
    """Call a registered tool directly (bypassing the LLM)."""
    service = get_agent_service()
    registry = service.registry

    tool_def = registry.get(tool_name)
    if tool_def is None:
        raise GeoFrontError(
            code="tool_not_found",
            message=f"Tool not found: {tool_name}",
            status_code=404,
        )

    import time

    from geoagent.registry import RunContext

    ctx = RunContext(
        store=service.store,
        workspace_dir=service._settings.workspace,
        sandbox_roots=service._settings.resolve_sandbox_roots(),
        settings=service._settings,
        max_tool_calls=1,
        deadline=time.monotonic() + tool_def.timeout_s,
    )

    result = registry.call(tool_name, body.args, ctx)
    return result.model_dump(mode="json")
