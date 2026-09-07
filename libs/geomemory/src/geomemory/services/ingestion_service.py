"""Ingestion service — orchestrates the ingest pipeline and job queue."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from geomemory.core.models import Job, SourceRef
from geomemory.ingest.job_queue import JobQueue
from geomemory.ingest.pipeline import IngestionPipeline
from geomemory.storage.object_store import ObjectStore


class IngestionService:
    """Public ingestion entry point: submit jobs and run the pipeline."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        objects: ObjectStore,
        *,
        pipeline: IngestionPipeline | None = None,
        jobs: JobQueue | None = None,
    ) -> None:
        self.conn = conn
        self.objects = objects
        self.pipeline = pipeline or IngestionPipeline(conn, objects)
        self.jobs = jobs or JobQueue(conn)

    def ingest(self, source: str | Path | bytes, collection_id: str) -> Job:
        """Submit and run an ingestion job synchronously."""
        source_ref = _to_source_ref(source)
        job = self.jobs.submit("ingestion", {"collection_id": collection_id})
        return self.jobs.run(job.id, lambda _j: self.pipeline.ingest_source(source_ref, collection_id))

    def ingest_batch(self, sources: list[str | Path], collection_id: str) -> Job:
        """Submit and run a batch ingestion job."""
        refs = [_to_source_ref(s) for s in sources]
        job = self.jobs.submit("ingestion", {"collection_id": collection_id, "count": len(refs)})
        return self.jobs.run(job.id, lambda _j: self.pipeline.ingest_batch(refs, collection_id))

    def get_job(self, job_id: str) -> Job | None:
        """Return a job by id."""
        return self.jobs.get(job_id)


def _to_source_ref(source: str | Path | bytes) -> SourceRef:
    if isinstance(source, bytes):
        return SourceRef(content_bytes=source)
    return SourceRef(path=str(source))
