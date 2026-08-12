"""Unit tests for the service layer."""

from __future__ import annotations

import hashlib

from geomemory.core.models import Job, SearchHit
from geomemory.services.job_service import JobService
from geomemory.services.search_service import SearchService as PublicSearchService


class TestJobService:
    def test_submit_and_get(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("indexing", {"space": "x"})
        assert job.state == "pending"
        assert svc.get_job(job.id).id == job.id

    def test_run_job(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("evaluation", {})
        done = svc.run_job(job.id, lambda j: {"ok": True})
        assert done.state == "completed"
        assert done.result == {"ok": True}

    def test_run_job_failure(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("evaluation", {})

        def _boom(job: Job):
            raise RuntimeError("boom")

        failed = svc.run_job(job.id, _boom)
        assert failed.state == "failed"
        assert "boom" in (failed.error or "")

    def test_cancel_and_list(self, temp_workspace):
        svc = JobService(temp_workspace.conn)
        job = svc.submit_job("ingestion", {})
        assert svc.cancel_job(job.id) is True
        assert svc.list_by_state("cancelled")[0].id == job.id


class TestPublicSearchService:
    def test_wraps_retrieval(self, temp_workspace):
        class _Retrieval:
            def search(self, query, *, mode="hybrid", top_k=20, top_n=5, filters=None):
                from geomemory.core.models import QueryPlan, SearchResult

                return SearchResult(
                    query=query, query_plan=QueryPlan(intent="search"), hits=[SearchHit(id="h1")]
                )

        svc = PublicSearchService(_Retrieval())
        result = svc.search("query", top_n=3)
        assert result.hits[0].id == "h1"