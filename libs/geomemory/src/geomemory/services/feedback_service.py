"""Feedback service — records feedback, manages review queue, exports datasets."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from geomemory.core.models import DatasetExample, FeedbackEvent
from geomemory.feedback.exporters import export_jsonl
from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository, FeedbackRepository


class FeedbackService:
    """Public feedback entry point."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.feedback_repo = FeedbackRepository(conn)
        self.dataset_repo = DatasetExampleRepository(conn)
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        self.candidate_service = CandidateMemoryService(conn)

    def record_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        """Record an immutable feedback event."""
        return self.feedback_repo.create(event)

    def get_review_queue(self) -> list[DatasetExample]:
        """Return pending dataset examples for review."""
        return self.dataset_repo.list_by_state("pending")

    def review(self, example_id: str, accept: bool, reviewer_id: str | None = None) -> bool:
        """Accept or reject a dataset example."""
        state = "accepted" if accept else "rejected"
        return self.dataset_repo.update_state(example_id, state, reviewer_id)

    def export_dataset(self, task_type: str, output_dir: str | Path) -> Path:
        """Export accepted examples for a task type to a JSONL file."""
        examples = self.dataset_repo.list_by_task(task_type)
        accepted = [e for e in examples if e.review_state == "accepted"]
        return export_jsonl(task_type, accepted, output_dir)

    def promote_to_candidate(self, event_ids: list[str], content: str, memory_type: str = "fact", author: str | None = None) -> Any:
        """Promote feedback events to a candidate memory with scoring."""
        from geomemory.feedback.scoring import MemoryScorer

        cm = self.candidate_service.create(content, memory_type=memory_type, source_feedback_ids=event_ids, author=author)
        scorer = MemoryScorer()
        # Simple signal: confirming count = len(event_ids)
        score = scorer.score(confirming=len(event_ids))
        self.candidate_service.score(cm.id, {"confirming": len(event_ids)})
        updated = self.candidate_service.get(cm.id)
        return updated or cm