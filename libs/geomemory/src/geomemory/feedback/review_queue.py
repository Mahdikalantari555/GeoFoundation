"""Review queue state machine for dataset examples."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Literal

from geomemory.core.models import DatasetExample
from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

ReviewState = Literal["pending", "accepted", "rejected"]

_VALID_STATES: set[str] = {"pending", "accepted", "rejected"}


class ReviewQueue:
    """Manage the lifecycle of dataset examples between review states.

    Raw feedback becomes a pending ``DatasetExample``; a reviewer moves it to
    ``accepted`` or ``rejected``. Only accepted examples are exported.
    """

    def __init__(self, conn: Connection, repo: DatasetExampleRepository | None = None) -> None:
        self.conn = conn
        self.repo = repo or DatasetExampleRepository(conn)

    def enqueue(self, example: DatasetExample) -> DatasetExample:
        """Add an example to the queue as pending."""
        if example.review_state != "pending":
            raise ValueError("Only pending examples can be enqueued")
        return self.repo.create(example)

    def pending(self) -> list[DatasetExample]:
        """Return all pending examples."""
        return self.repo.list_by_state("pending")

    def accepted(self, task_type: str | None = None) -> list[DatasetExample]:
        """Return all accepted examples, optionally for a task type."""
        examples = self.repo.list_by_state("accepted")
        if task_type is not None:
            examples = [e for e in examples if e.task_type == task_type]
        return examples

    def review(self, example_id: str, accept: bool, reviewer_id: str | None = None) -> bool:
        """Review an example. Returns True when the state changed."""
        state = "accepted" if accept else "rejected"
        return self.repo.update_state(example_id, state, reviewer_id)

    def reject(self, example_id: str, reviewer_id: str | None = None) -> bool:
        """Reject an example."""
        return self.repo.update_state(example_id, "rejected", reviewer_id)

    def get(self, example_id: str) -> DatasetExample | None:
        """Return an example by id."""
        return self.repo.get(example_id)

    def count_by_state(self, state: str) -> int:
        """Return the number of examples in a state."""
        if state not in _VALID_STATES:
            raise ValueError(f"Unknown review state: {state}")
        return len(self.repo.list_by_state(state))
