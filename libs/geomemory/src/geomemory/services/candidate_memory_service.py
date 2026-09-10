"""CandidateMemoryService — CRUD + scoring + proposal wiring."""

from __future__ import annotations

import sqlite3
from typing import Any

from geomemory.core.models import CandidateMemory
from geomemory.feedback.candidate_memory import CandidateMemoryRepository
from geomemory.feedback.proposals import ProposalEngine
from geomemory.feedback.scoring import MemoryScorer


class CandidateMemoryService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.repo = CandidateMemoryRepository(conn)
        self.scorer = MemoryScorer()
        self.proposals = ProposalEngine(conn)

    def create(self, content: str, memory_type: str = "fact", source_feedback_ids: list[str] | None = None, author: str | None = None) -> CandidateMemory:
        cm = CandidateMemory(content=content, memory_type=memory_type, source_feedback_ids=source_feedback_ids or [], author=author)  # type: ignore[arg-type]
        return self.repo.create(cm)

    def get(self, cm_id: str) -> CandidateMemory | None:
        return self.repo.get(cm_id)

    def list(self, state: str | None = None) -> list[CandidateMemory]:
        return self.repo.list(state)

    def promote(self, cm_id: str, new_state: str, reviewer_id: str | None = None, note: str | None = None) -> CandidateMemory | None:
        updated = self.repo.promote(cm_id, new_state, reviewer_id, note)
        if updated and new_state == "verified":
            self.proposals.generate(updated)
        return updated

    def score(self, cm_id: str, signals: dict[str, Any] | None = None) -> float:
        cm = self.repo.get(cm_id)
        if not cm:
            raise ValueError(f"Candidate not found: {cm_id}")
        signals = signals or {}
        score = self.scorer.compute_from_payload(signals) if signals else cm.confidence_score
        self.repo.update_score(cm_id, score)
        # auto state based on thresholds if not rejected
        if cm.state != "rejected":
            new_state = self.scorer.state_for(score)
            if new_state != cm.state:
                # allow forward promotion or backward drop via score change
                self.repo.promote(cm_id, new_state, None, f"auto score {score}", allow_regression=True)
        updated = self.repo.get(cm_id)
        return updated.confidence_score if updated else score

    def search(self, query: str, min_score: float = 0) -> list[CandidateMemory]:
        return self.repo.search(query, min_score)
