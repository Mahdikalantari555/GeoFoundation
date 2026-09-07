from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from geomemory import GeoMemory, GeoMemoryError
from geomemory.core.models import FeedbackEvent

from ..errors import GeoFrontError
from ..schemas import FeedbackRequest
from ..state import get_state

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=201)
async def record_feedback(req: FeedbackRequest) -> dict[str, object]:
    """Record an immutable feedback event (search hit thumbs, answer ratings)."""
    ws: GeoMemory = get_state().require_workspace()
    event = FeedbackEvent(
        target_type=req.target_type,
        target_id=req.target_id,
        label=req.label,
        actor=req.actor,
        payload=req.payload,
        metadata=req.metadata,
    )
    async with get_state().write_lock:
        try:
            stored = await run_in_threadpool(ws.record_feedback, event)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="feedback_failed", message=str(exc)) from exc
    return stored.model_dump(mode="json")


@router.get("/candidates")
async def list_candidates(state: str | None = None) -> list[dict[str, Any]]:
    ws: GeoMemory = get_state().require_workspace()
    def _list() -> list[dict[str, Any]]:
        from geomemory.services.candidate_memory_service import CandidateMemoryService
        svc = CandidateMemoryService(ws.conn)
        return [c.model_dump(mode="json") for c in svc.list(state)]
    return await run_in_threadpool(_list)


@router.post("/candidates")
async def create_candidate(body: dict[str, Any]) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    def _create() -> dict[str, Any]:
        from geomemory.services.candidate_memory_service import CandidateMemoryService
        svc = CandidateMemoryService(ws.conn)
        cm = svc.create(body.get("content", ""), memory_type=body.get("memory_type", "fact"), source_feedback_ids=body.get("source_feedback_ids", []), author=body.get("author"))
        # optional scoring
        if body.get("signals"):
            svc.score(cm.id, body["signals"])
            cm = svc.get(cm.id) or cm
        return cm.model_dump(mode="json")
    async with get_state().write_lock:
        return await run_in_threadpool(_create)


@router.post("/candidates/{cid}/review")
async def review_candidate(cid: str, body: dict[str, Any]) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    new_state = body.get("new_state") or body.get("state")
    reviewer_id = body.get("reviewer_id")
    note = body.get("note")
    signals = body.get("signals")
    def _review() -> dict[str, Any]:
        from geomemory.services.candidate_memory_service import CandidateMemoryService
        svc = CandidateMemoryService(ws.conn)
        if signals:
            svc.score(cid, signals)
        updated = svc.promote(cid, new_state, reviewer_id, note) if new_state else svc.get(cid)
        if not updated:
            raise GeoFrontError(code="not_found", message=f"Candidate {cid} not found", status_code=404)
        return updated.model_dump(mode="json")
    async with get_state().write_lock:
        return await run_in_threadpool(_review)


@router.get("/proposals")
async def list_proposals(status: str | None = None) -> list[dict[str, Any]]:
    ws: GeoMemory = get_state().require_workspace()
    def _list() -> list[dict[str, Any]]:
        from geomemory.feedback.proposals import ProposalEngine
        eng = ProposalEngine(ws.conn)
        return [p.model_dump(mode="json") for p in eng.list(status)]
    return await run_in_threadpool(_list)


@router.post("/proposals/{pid}/approve")
async def approve_proposal(pid: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    reviewer_id = (body or {}).get("reviewer_id")
    note = (body or {}).get("note")
    def _approve() -> dict[str, Any]:
        from geomemory.feedback.proposals import ProposalEngine
        eng = ProposalEngine(ws.conn)
        res = eng.review(pid, True, reviewer_id, note)
        if not res:
            raise GeoFrontError(code="not_found", message=f"Proposal {pid} not found", status_code=404)
        return res.model_dump(mode="json")
    async with get_state().write_lock:
        return await run_in_threadpool(_approve)


@router.post("/proposals/{pid}/reject")
async def reject_proposal(pid: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    reviewer_id = (body or {}).get("reviewer_id")
    note = (body or {}).get("note")
    def _reject() -> dict[str, Any]:
        from geomemory.feedback.proposals import ProposalEngine
        eng = ProposalEngine(ws.conn)
        res = eng.review(pid, False, reviewer_id, note)
        if not res:
            raise GeoFrontError(code="not_found", message=f"Proposal {pid} not found", status_code=404)
        return res.model_dump(mode="json")
    async with get_state().write_lock:
        return await run_in_threadpool(_reject)


@router.get("/export")
async def export_feedback(task_type: str, output_dir: str | None = None) -> FileResponse:
    """Export accepted feedback examples for a task type as a downloadable JSONL."""
    ws = get_state().require_workspace()
    out = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
    out.mkdir(parents=True, exist_ok=True)
    async with get_state().write_lock:
        try:
            path = await run_in_threadpool(ws.export_dataset, task_type, out)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="feedback_export_failed", message=str(exc)) from exc
        except ValueError as exc:
            raise GeoFrontError(
                code="feedback_export_empty",
                message=str(exc),
                status_code=404,
            ) from exc
    return FileResponse(path, filename=path.name, media_type="application/jsonl")
