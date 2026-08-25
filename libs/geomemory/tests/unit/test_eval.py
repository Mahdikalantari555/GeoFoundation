"""Tests for the evaluation modules: metrics, benchmark, runner, reporters."""

from __future__ import annotations

import json

from geomemory.core.models import BenchmarkResult, Citation, SearchHit
from geomemory.eval.benchmark import BenchmarkItem, load_benchmark, to_jsonl
from geomemory.eval.qa_metrics import (
    abstention_accuracy,
    citation_correctness,
    faithfulness_proxy,
)
from geomemory.eval.reporter import json_report, markdown_report
from geomemory.eval.retrieval_metrics import mrr_at_k, ndcg_at_k, precision_at_k, recall_at_k
from geomemory.eval.runner import BenchmarkRunner


class TestRetrievalMetrics:
    def test_recall_at_k(self):
        assert recall_at_k(["a", "b"], ["a", "c", "b"], k=2) == 0.5

    def test_recall_no_gold(self):
        assert recall_at_k([], ["a"]) == 0.0

    def test_precision_at_k(self):
        assert precision_at_k(["a", "c"], ["a", "b", "c"], k=3) == 2 / 3

    def test_mrr_at_k(self):
        assert mrr_at_k(["c"], ["a", "b", "c"], k=3) == 1 / 3
        assert mrr_at_k(["c"], ["a", "b"], k=2) == 0.0

    def test_ndcg_at_k(self):
        # Relevant [a] at rank 1: perfect DCG.
        assert ndcg_at_k(["a"], ["a"], k=1) == 1.0
        assert ndcg_at_k(["a"], ["b", "a"], k=2) > 0.0


class TestQaMetrics:
    def test_abstention_accuracy(self):
        assert abstention_accuracy([True, False], [True, False]) == 1.0
        assert abstention_accuracy([True], [False]) == 0.0

    def test_citation_correctness(self):
        c1 = Citation(answer_id="", segment_id="good")
        c2 = Citation(answer_id="", segment_id="bad")
        assert citation_correctness([c1, c2], ["good"]) == 0.5

    def test_faithfulness_proxy(self):
        text = "Flood extent [1] and land use [2]"
        assert faithfulness_proxy(text, ["s1", "s2"]) == 1.0
        assert faithfulness_proxy(text, ["s1", "s2"], gold_ids=["s1"]) == 0.5
        # Key out of context range is unfaithful.
        assert faithfulness_proxy("Missing [5]", ["s1"]) == 0.0


class TestBenchmarkLoad:
    def test_load_and_iter(self, tmp_path):
        p = tmp_path / "b.jsonl"
        p.write_text(json.dumps({"query": "q1", "gold_ids": ["g1"]}) + "\n", encoding="utf-8")
        bench = load_benchmark(p)
        assert bench.name == "b"
        assert len(bench) == 1
        assert isinstance(bench[0], BenchmarkItem)

    def test_to_jsonl_roundtrip(self):
        rows = [{"query": "q", "gold_ids": []}]
        assert json.loads(to_jsonl(rows)) == rows[0]

    def test_empty_query_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            BenchmarkItem(query="   ")


class _FakeWorkspace:
    """Workspace double that returns gold ids in a fixed order."""

    def search(self, query, **kwargs):
        return SearchResultStub(hits=[SearchHit(id=f"h{i}") for i in range(3)])

    def ask(self, question):
        from geomemory.core.models import QAResult

        return QAResult(text="not found in selected sources", abstained=True)


class SearchResultStub:
    def __init__(self, hits):
        self.hits = hits


class TestRunner:
    def test_run_returns_result(self, tmp_path):
        p = tmp_path / "rb.jsonl"
        p.write_text(
            json.dumps({"query": "q", "gold_ids": ["h0", "h1"]}) + "\n", encoding="utf-8"
        )
        runner = BenchmarkRunner(_FakeWorkspace())
        result = runner.run(str(p))
        assert isinstance(result, BenchmarkResult)
        assert "retrieval" in result.metrics
        assert result.metrics["retrieval"]["recall@5"] == 1.0

    def test_qa_abstention(self, tmp_path):
        p = tmp_path / "qb.jsonl"
        p.write_text(
            json.dumps({"query": "q", "expected_abstain": True}) + "\n", encoding="utf-8"
        )
        runner = BenchmarkRunner(_FakeWorkspace())
        result = runner.run(str(p))
        assert result.metrics["qa"]["abstain_rate"] == 1.0


class TestReporters:
    def test_json_report(self):
        out = json_report("b", {"retrieval": {"recall@1": 0.5}})
        assert json.loads(out)["metrics"]["retrieval"]["recall@1"] == 0.5

    def test_markdown_report(self):
        out = markdown_report("b", {"retrieval": {"recall@1": 0.5}})
        assert "# Benchmark: b" in out
        assert "0.500" in out
