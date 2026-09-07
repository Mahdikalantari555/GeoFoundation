"""Job service — manages background job lifecycle."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from geomemory.core.models import Job
from geomemory.ingest.job_queue import JobQueue


class JobService:
    """Public job management entry point."""

    def __init__(self, conn: sqlite3.Connection, jobs: JobQueue | None = None) -> None:
        self.jobs = jobs or JobQueue(conn)

    def submit_job(self, job_type: str, input_data: dict[str, Any]) -> Job:
        """Submit a new job."""
        return self.jobs.submit(job_type, input_data)

    def run_job(self, job_id: str, fn: Callable[[Job], dict[str, Any]]) -> Job:
        """Run a job synchronously."""
        return self.jobs.run(job_id, fn)

    def get_job(self, job_id: str) -> Job | None:
        """Return a job by id."""
        return self.jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending/running job."""
        return self.jobs.cancel(job_id)

    def list_by_state(self, state: str) -> list[Job]:
        """Return jobs in a given state."""
        return self.jobs.list_by_state(state)
