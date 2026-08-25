"""Background job management with progress, cancellation, and checkpoint resume."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Callable

from geomemory.core.models import Job

_JOB_COLUMNS = (
    "id, type, state, progress, input, result, error, checkpoint, created_at, updated_at"
)


class JobQueue:
    """SQLite-backed job queue with in-process worker threads.

    Jobs are persisted so interrupted runs can be resumed from a checkpoint.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._lock = threading.Lock()

    def submit(self, job_type: str, input_data: dict[str, Any]) -> Job:
        """Create a new pending job."""
        job = Job(type=job_type, input=input_data)
        with self._lock:
            self.conn.execute(
                f"INSERT INTO job ({_JOB_COLUMNS}) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)",
                (
                    job.id,
                    job.type,
                    job.state,
                    job.progress,
                    json.dumps(job.input),
                    job.created_at,
                    job.updated_at,
                ),
            )
            self.conn.commit()
        return job

    def get(self, job_id: str) -> Job | None:
        """Fetch a job by id."""
        row = self.conn.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
        return self._load(row) if row is not None else None

    def list_by_state(self, state: str) -> list[Job]:
        """Return jobs in a given state."""
        rows = self.conn.execute(
            "SELECT * FROM job WHERE state = ? ORDER BY created_at", (state,)
        ).fetchall()
        return [self._load(r) for r in rows]

    def update_state(self, job_id: str, state: str, *, error: str | None = None) -> None:
        """Update a job's state and optional error."""
        with self._lock:
            self.conn.execute(
                "UPDATE job SET state = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
                (state, error, job_id),
            )
            self.conn.commit()

    def update_progress(self, job_id: str, progress: float, *, checkpoint: dict[str, Any] | None = None) -> None:
        """Update a job's progress and optional checkpoint."""
        with self._lock:
            self.conn.execute(
                "UPDATE job SET progress = ?, checkpoint = ?, updated_at = datetime('now') WHERE id = ?",
                (progress, json.dumps(checkpoint) if checkpoint else None, job_id),
            )
            self.conn.commit()

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        """Mark a job completed with a result."""
        with self._lock:
            self.conn.execute(
                "UPDATE job SET state = 'completed', result = ?, progress = 1.0, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(result), job_id),
            )
            self.conn.commit()

    def fail(self, job_id: str, error: str) -> None:
        """Mark a job failed with an error message."""
        self.update_state(job_id, "failed", error=error)

    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/running job. Returns True if cancelled."""
        cur = self.conn.execute(
            "UPDATE job SET state = 'cancelled', updated_at = datetime('now') "
            "WHERE id = ? AND state IN ('pending', 'running')",
            (job_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def run(self, job_id: str, fn: Callable[[Job], dict[str, Any]]) -> Job:
        """Execute a job synchronously, updating state along the way."""
        job = self.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        self.update_state(job_id, "running")
        try:
            result = fn(job)
            self.complete(job_id, result)
        except Exception as exc:  # noqa: BLE001 - job boundary
            self.fail(job_id, str(exc))
        return self.get(job_id)  # type: ignore[return-value]

    def _load(self, row: sqlite3.Row) -> Job:
        data = dict(row)
        data["input"] = json.loads(data["input"] or "{}")
        data["result"] = json.loads(data["result"]) if data.get("result") else None
        data["checkpoint"] = json.loads(data["checkpoint"]) if data.get("checkpoint") else None
        return Job(**data)