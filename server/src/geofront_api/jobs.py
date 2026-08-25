from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobRecord:
    id: str
    type: str
    status: str = "pending"  # pending | running | completed | failed
    progress: float = 0.0
    result: Any | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "progress": self.progress,
        }
        if self.result is not None:
            body["result"] = self.result
        if self.error is not None:
            body["error"] = self.error
        return body


@dataclass
class JobManager:
    """In-process background job registry.

    Jobs run blocking callables in a threadpool; status is queryable by id.
    Single-user local platform: no persistence, no pruning strategy needed
    beyond a size cap.
    """

    _jobs: dict[str, JobRecord] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _max_records: int = 256

    async def submit(self, job_type: str, fn: Callable[[], Any]) -> JobRecord:
        """Run `fn` in a background thread; return the job record immediately."""
        record = JobRecord(id=uuid.uuid4().hex[:12], type=job_type)

        async with self._lock:
            # Evict oldest terminal jobs when over the cap.
            if len(self._jobs) >= self._max_records:
                terminal = [
                    k
                    for k, v in self._jobs.items()
                    if v.status in ("completed", "failed")
                ]
                for key in terminal[: len(self._jobs) - self._max_records + 1]:
                    self._jobs.pop(key, None)
                    self._tasks.pop(key, None)
            self._jobs[record.id] = record

        async def _run() -> None:
            record.status = "running"
            try:
                record.result = await asyncio.to_thread(fn)
                record.status = "completed"
                record.progress = 1.0
            except Exception as exc:  # noqa: BLE001 — surfaced via job record
                record.status = "failed"
                record.error = str(exc)

        self._tasks[record.id] = asyncio.create_task(_run())
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def wait_for(self, job_id: str, timeout: float = 120.0) -> JobRecord:
        """Block until a job reaches a terminal state (tests / internal use)."""
        import asyncio as _asyncio

        record = self._jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        task = self._tasks.get(job_id)
        if task is not None:
            await _asyncio.wait_for(_asyncio.shield(task), timeout=timeout)
        return record

    async def aclose(self) -> None:
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        for task in self._tasks.values():
            with contextlib.suppress(BaseException):
                await task


_manager: JobManager | None = None


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager()
    return _manager


def reset_job_manager() -> None:
    global _manager
    _manager = None
