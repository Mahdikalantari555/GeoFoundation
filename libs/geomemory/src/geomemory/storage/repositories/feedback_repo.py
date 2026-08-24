"""Feedback event and dataset example repository."""

from __future__ import annotations

import json
import sqlite3

from geomemory.core.models import DatasetExample, FeedbackEvent


class FeedbackRepository:
    """Append-only CRUD for feedback events."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, event: FeedbackEvent) -> FeedbackEvent:
        """Insert a feedback event (append-only)."""
        self.conn.execute(
            "INSERT INTO feedback_event (id, target_type, target_id, actor, label, payload, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.id,
                event.target_type,
                event.target_id,
                event.actor,
                event.label,
                json.dumps(event.payload),
                event.created_at,
                json.dumps(event.metadata),
            ),
        )
        self.conn.commit()
        return event

    def get(self, event_id: str) -> FeedbackEvent | None:
        """Fetch a feedback event by id."""
        row = self.conn.execute(
            "SELECT * FROM feedback_event WHERE id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["payload"] = json.loads(data["payload"] or "{}")
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return FeedbackEvent(**data)

    def list_by_target(self, target_type: str, target_id: str) -> list[FeedbackEvent]:
        """Return all events for a target."""
        rows = self.conn.execute(
            "SELECT * FROM feedback_event WHERE target_type = ? AND target_id = ? ORDER BY created_at",
            (target_type, target_id),
        ).fetchall()
        return [self._load(r) for r in rows]

    def list_all(self, limit: int = 1000) -> list[FeedbackEvent]:
        """Return recent events."""
        rows = self.conn.execute(
            "SELECT * FROM feedback_event ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._load(r) for r in rows]

    def count(self) -> int:
        """Return the total number of events."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM feedback_event").fetchone()
        return int(row["c"]) if row is not None else 0

    def _load(self, row: sqlite3.Row) -> FeedbackEvent:
        data = dict(row)
        data["payload"] = json.loads(data["payload"] or "{}")
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return FeedbackEvent(**data)


class DatasetExampleRepository:
    """CRUD for dataset examples (review queue)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, example: DatasetExample) -> DatasetExample:
        """Insert a dataset example."""
        self.conn.execute(
            "INSERT INTO dataset_example "
            "(id, task_type, source_feedback_ids, review_state, reviewer_id, reviewed_at, version, dataset_card, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                example.id,
                example.task_type,
                json.dumps(example.source_feedback_ids),
                example.review_state,
                example.reviewer_id,
                example.reviewed_at,
                example.version,
                json.dumps(example.dataset_card) if example.dataset_card else None,
                example.created_at,
                example.updated_at,
            ),
        )
        self.conn.commit()
        return example

    def get(self, example_id: str) -> DatasetExample | None:
        """Fetch a dataset example by id."""
        row = self.conn.execute(
            "SELECT * FROM dataset_example WHERE id = ?", (example_id,)
        ).fetchone()
        if row is None:
            return None
        return self._load(row)

    def list_by_state(self, review_state: str) -> list[DatasetExample]:
        """Return examples in a given review state."""
        rows = self.conn.execute(
            "SELECT * FROM dataset_example WHERE review_state = ? ORDER BY created_at",
            (review_state,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def list_by_task(self, task_type: str) -> list[DatasetExample]:
        """Return examples for a task type."""
        rows = self.conn.execute(
            "SELECT * FROM dataset_example WHERE task_type = ? ORDER BY created_at",
            (task_type,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def update_state(self, example_id: str, review_state: str, reviewer_id: str | None = None) -> bool:
        """Update the review state of an example."""
        cur = self.conn.execute(
            "UPDATE dataset_example SET review_state = ?, reviewer_id = ?, reviewed_at = datetime('now'), "
            "updated_at = datetime('now') WHERE id = ?",
            (review_state, reviewer_id, example_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def _load(self, row: sqlite3.Row) -> DatasetExample:
        data = dict(row)
        data["source_feedback_ids"] = json.loads(data["source_feedback_ids"] or "[]")
        data["dataset_card"] = json.loads(data["dataset_card"]) if data.get("dataset_card") else None
        return DatasetExample(**data)