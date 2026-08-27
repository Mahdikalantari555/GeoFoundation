"""Agent playbooks route: list, get, run, and save playbooks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/playbooks", tags=["agent"])


def _require_initialized(service: Any) -> None:
    if not service.is_initialized:
        raise GeoFrontError(
            code="agent_not_ready",
            message="Agent not initialized. Open a workspace first.",
            status_code=409,
        )


@router.get("")
async def list_playbooks() -> dict[str, object]:
    """List all playbooks with validation status."""
    from geoagent import playbooks as pb_mod

    service = get_agent_service()
    _require_initialized(service)

    found = pb_mod.load_playbooks(service._settings.workspace)
    registry = service.registry

    items = []
    for pb in found:
        problems = pb_mod.validate_playbook(pb, registry)
        items.append({
            "name": pb.name,
            "version": pb.version,
            "triggers": pb.triggers,
            "params": pb.params,
            "steps": [{"tool": s.tool, "args": s.args} for s in pb.steps],
            "valid": len(problems) == 0,
            "problems": problems,
            "source_path": pb.source_path,
        })

    return {"playbooks": items}


@router.get("/{name}")
async def get_playbook(name: str) -> dict[str, object]:
    """Get a specific playbook by name."""
    from geoagent import playbooks as pb_mod

    service = get_agent_service()
    _require_initialized(service)

    target = service._settings.workspace / "playbooks" / f"{name.replace('-', '_')}.md"
    if not target.exists():
        raise GeoFrontError(
            code="playbook_not_found",
            message=f"Playbook not found: {name}",
            status_code=404,
        )

    text = target.read_text(encoding="utf-8")
    pb = pb_mod.parse_playbook(text, str(target))
    problems = pb_mod.validate_playbook(pb, service.registry)

    return {
        "name": pb.name,
        "version": pb.version,
        "triggers": pb.triggers,
        "params": pb.params,
        "steps": [{"tool": s.tool, "args": s.args} for s in pb.steps],
        "valid": len(problems) == 0,
        "problems": problems,
        "source_path": str(target),
        "content": text,
    }


class RunPlaybookRequest(BaseModel):
    params: dict[str, Any] = {}


@router.post("/{name}/run")
async def run_playbook(name: str, body: RunPlaybookRequest) -> dict[str, object]:
    """Run a playbook directly (no LLM involved)."""
    service = get_agent_service()
    registry = service.registry

    tool_name = f"pb_{name.replace('-', '_')}"
    tool_def = registry.get(tool_name)
    if tool_def is None:
        raise GeoFrontError(
            code="playbook_not_found",
            message=f"Playbook not found: {name}",
            status_code=404,
        )

    import time

    from geoagent.registry import RunContext

    ctx = RunContext(
        store=service.store,
        workspace_dir=service._settings.workspace,
        sandbox_roots=service._settings.resolve_sandbox_roots(),
        settings=service._settings,
        max_tool_calls=500,
        deadline=time.monotonic() + 880.0,
    )

    result = registry.call(tool_name, body.params, ctx)
    return result.model_dump(mode="json")


class SavePlaybookRequest(BaseModel):
    name: str
    content: str


@router.post("/save")
async def save_playbook(req: SavePlaybookRequest) -> dict[str, object]:
    """Save a new playbook."""
    from geoagent import playbooks as pb_mod

    service = get_agent_service()
    _require_initialized(service)

    # Validate the playbook content
    pb = pb_mod.parse_playbook(req.content)
    problems = pb_mod.validate_playbook(pb, service.registry)

    if problems:
        raise GeoFrontError(
            code="invalid_playbook",
            message=f"Playbook validation failed: {'; '.join(problems[:5])}",
            status_code=422,
            detail={"problems": problems},
        )

    path = pb_mod.save_playbook(service._settings.workspace, req.name, req.content)
    return {"saved": str(path), "name": pb.name}
