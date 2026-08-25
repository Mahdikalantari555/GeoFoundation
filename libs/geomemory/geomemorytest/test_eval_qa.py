"""Eval and QA service tests: retrieval metrics, QA metrics, benchmark, runner, reporter."""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------
from geomemory.eval.retrieval_metrics import (
    mrr_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


class TestRecallAtK:
    def test_empty_relevant_returns_zero(self):
        assert recall_at_k([], ["a", "b"]) == 0.0

    def test_empty_retrieved_returns_zero(self):
        assert recall_at_k(["a"], []) == 0.0

    def test_perfect_recall(self):
        assert recall_at_k(["a", "b"], ["a", "b", "c"]) == 1.0

    def test_partial_recall(self):
        assert recall_at_k(["a", "b"], ["a", "c"]) == 0.5

    def test_no_recall(self):
        assert recall_at_k(["a"], ["b", "c"]) == 0.0

    def test_k_none_uses_all(self):
        assert recall_at_k(["a"], ["a", "b"], k=None) == 1.0

    def test_k_limits_results(self):
        assert recall_at_k(["a", "b"], ["a", "b", "c"], k=1) == 0.5

    def test_k_larger_than_retrieved(self):
        assert recall_at_k(["a"], ["a"], k=10) == 1.0


class TestPrecisionAtK:
    def test_empty_relevant_returns_zero(self):
        assert precision_at_k([], ["a"]) == 0.0

    def test_empty_retrieved_returns_zero(self):
        assert precision_at_k(["a"], []) == 0.0

    def test_perfect_precision(self):
        assert precision_at_k(["a", "b"], ["a", "b"]) == 1.0

    def test_partial_precision(self):
        assert precision_at_k(["a"], ["a", "b"]) == 0.5

    def test_zero_precision(self):
        assert precision_at_k(["a"], ["b", "c"]) == 0.0

    def test_k_none(self):
        assert precision_at_k(["a"], ["a", "b"], k=None) == 0.5

    def test_k_limits(self):
        assert precision_at_k(["a", "b"], ["a", "c", "b"], k=1) == 1.0


class TestMrrAtK:
    def test_empty_relevant(self):
        assert mrr_at_k([], ["a"]) == 0.0

    def test_first_rank(self):
        assert mrr_at_k(["a"], ["a", "b"]) == 1.0

    def test_second_rank(self):
        assert mrr_at_k(["b"], ["a", "b"]) == 0.5

    def test_no_relevant(self):
        assert mrr_at_k(["a"], ["b", "c"]) == 0.0

    def test_k_none(self):
        assert mrr_at_k(["a"], ["b", "a"], k=None) == 0.5

    def test_k_limits(self):
        assert mrr_at_k(["b"], ["b", "a"], k=1) == 1.0

    def test_k_excludes_result(self):
        assert mrr_at_k(["b"], ["a", "b"], k=1) == 0.0


class TestNdcgAtK:
    def test_empty_relevant(self):
        assert ndcg_at_k([], ["a"]) == 0.0

    def test_empty_retrieved(self):
        assert ndcg_at_k(["a"], []) == 0.0

    def test_perfect_ranking(self):
        # Ideal DCG = 1 + 1/2 = 1.5, DCG same.
        assert ndcg_at_k(["a", "b"], ["a", "b"]) == pytest.approx(1.0)

    def test_imperfect_ranking(self):
        # One gold item at rank 2: DCG = 1/log2(3), IDCG = 1/log2(2).
        result = ndcg_at_k(["a"], ["b", "a"], k=2)
        expected = (1.0 / math.log2(3)) / (1.0 / math.log2(2))
        assert result == pytest.approx(expected)

    def test_no_relevant(self):
        assert ndcg_at_k(["a"], ["b", "c"]) == 0.0

    def test_k_none(self):
        assert ndcg_at_k(["a"], ["a", "b"], k=None) == pytest.approx(1.0)

    def test_k_limits(self):
        assert ndcg_at_k(["a"], ["b", "a", "c"], k=2) == pytest.approx(1.0 / math.log2(3) / 1.0)


# ---------------------------------------------------------------------------
# QA metrics
# ---------------------------------------------------------------------------
from geomemory.eval.qa_metrics import (
    abstain_rate,
    abstention_accuracy,
    citation_correctness,
    faithfulness_proxy,
)


class TestAbstentionAccuracy:
    def test_empty_returns_zero(self):
        assert abstention_accuracy([], []) == 0.0

    def test_perfect_match(self):
        assert abstention_accuracy([True, False], [True, False]) == 1.0

    def test_no_match(self):
        assert abstention_accuracy([True, False], [False, True]) == 0.0

    def test_partial(self):
        assert abstention_accuracy([True, False, True], [True, True, False]) == pytest.approx(1 / 3)


class TestCitationCorrectness:
    def test_empty_citations_returns_zero(self):
        assert citation_correctness([], ["a", "b"]) == 0.0

    def test_empty_gold_returns_zero(self):
        assert citation_correctness([mock.MagicMock(segment_id="a")], []) == 0.0

    def test_all_correct(self):
        cits = [mock.MagicMock(segment_id="a"), mock.MagicMock(segment_id="b")]
        assert citation_correctness(cits, ["a", "b"]) == 1.0

    def test_partial_correct(self):
        cits = [mock.MagicMock(segment_id="a"), mock.MagicMock(segment_id="c")]
        assert citation_correctness(cits, ["a", "b"]) == 0.5


class TestFaithfulnessProxy:
    def test_empty_keys_returns_zero(self):
        assert faithfulness_proxy("no citations", ["a", "b"]) == 0.0

    def test_all_valid_without_gold(self):
        text = "answer [1] and [2]"
        assert faithfulness_proxy(text, ["a", "b"]) == 1.0

    def test_out_of_range_key_ignored(self):
        text = "answer [2]"
        assert faithfulness_proxy(text, ["a"]) == 0.0

    def test_with_gold_ids(self):
        text = "answer [1]"
        assert faithfulness_proxy(text, ["a", "b"], gold_ids=["a"]) == 1.0

    def test_key_not_in_gold(self):
        text = "answer [1]"
        assert faithfulness_proxy(text, ["a", "b"], gold_ids=["c"]) == 0.0

    def test_empty_gold_with_gold_param(self):
        assert faithfulness_proxy("answer [1]", ["a"], gold_ids=[]) == 0.0


class TestAbstainRate:
    def test_empty_returns_zero(self):
        assert abstain_rate([]) == 0.0

    def test_all_abstain(self):
        assert abstain_rate(["not found in the provided context", "i don't know"]) == 1.0

    def test_none_abstain(self):
        assert abstain_rate(["the answer is 42", "NDVI is high"]) == 0.0

    def test_partial(self):
        assert abstain_rate(["i do not know", "answer"]) == 0.5


# ---------------------------------------------------------------------------
# Abstention module
# ---------------------------------------------------------------------------
from geomemory.qa.abstention import abstention_reason, should_abstain


class TestShouldAbstain:
    def test_detects_not_found_in_sources(self):
        assert should_abstain("Not found in selected sources")

    def test_detects_i_do_not_know(self):
        assert should_abstain("I do not know the answer")

    def test_detects_cannot_answer(self):
        assert should_abstain("Cannot answer based on the context")

    def test_detects_insufficient_information(self):
        assert should_abstain("Insufficient information to respond")

    def test_no_abstain_phrases(self):
        assert not should_abstain("The NDVI value is 0.8")

    def test_empty_string(self):
        assert not should_abstain("")

    def test_case_insensitive(self):
        assert should_abstain("I DON'T KNOW")


class TestAbstentionReason:
    def test_empty_string(self):
        assert abstention_reason("") == "Empty answer generated"

    def test_non_empty(self):
        assert "insufficient evidence" in abstention_reason("some answer")


# ---------------------------------------------------------------------------
# Citation module
# ---------------------------------------------------------------------------
from geomemory.qa.citation import extract_citation_keys, map_citations, validate_citations


class TestExtractCitationKeys:
    def test_no_citations(self):
        assert extract_citation_keys("no refs") == []

    def test_single_citation(self):
        assert extract_citation_keys("see [1]") == [1]

    def test_multiple_citations(self):
        assert extract_citation_keys("see [1] and [2] and [10]") == [1, 2, 10]

    def test_non_numeric_ignored(self):
        assert extract_citation_keys("see [a] and [1]") == [1]


class TestMapCitations:
    def test_empty_keys_returns_empty(self):
        assert map_citations("ans1", "no refs", []) == []

    def test_maps_correctly(self):
        sources = [
            mock.MagicMock(id="seg1", locator={"text": "page 1"}),
            mock.MagicMock(id="seg2", locator={"text": "page 2"}),
        ]
        result = map_citations("ans1", "see [1] and [2]", sources)
        assert len(result) == 2
        assert result[0].segment_id == "seg1"
        assert result[1].segment_id == "seg2"

    def test_out_of_range_key_ignored(self):
        sources = [mock.MagicMock(id="seg1", locator="page 1")]
        result = map_citations("ans1", "see [2]", sources)
        assert result == []


class TestValidateCitations:
    def test_empty_lists(self):
        assert validate_citations([], []) is True

    def test_all_valid(self):
        sources = [mock.MagicMock(id="a"), mock.MagicMock(id="b")]
        cits = [mock.MagicMock(segment_id="a"), mock.MagicMock(segment_id="b")]
        assert validate_citations(cits, sources) is True

    def test_invalid_citation(self):
        sources = [mock.MagicMock(id="a")]
        cits = [mock.MagicMock(segment_id="c")]
        assert validate_citations(cits, sources) is False


# ---------------------------------------------------------------------------
# Benchmark module
# ---------------------------------------------------------------------------
from geomemory.eval.benchmark import BenchmarkItem, load_benchmark, to_jsonl


class TestBenchmarkItem:
    def test_valid_item(self):
        item = BenchmarkItem(query="test query", gold_ids=["a", "b"])
        assert item.query == "test query"
        assert item.gold_ids == ["a", "b"]

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="query must not be empty"):
            BenchmarkItem(query="   ")

    def test_defaults(self):
        item = BenchmarkItem(query="q")
        assert item.reference_answer == ""
        assert item.expected_abstain is False
        assert item.metadata == {}


class TestLoadBenchmark:
    def test_loads_jsonl(self, tmp_path: Path):
        p = tmp_path / "bench.jsonl"
        p.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
            + json.dumps({"query": "q2", "gold_ids": ["b"]}) + "\n"
        )
        bench = load_benchmark(str(p))
        assert bench.name == "bench"
        assert len(bench) == 2
        assert bench[0].query == "q1"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_benchmark("/nonexistent/path.jsonl")

    def test_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.jsonl"
        p.write_text("not json\n")
        with pytest.raises(ValueError, match="invalid JSON"):
            load_benchmark(str(p))

    def test_empty_file_raises(self, tmp_path: Path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        with pytest.raises(ValueError, match="no items"):
            load_benchmark(str(p))


class TestToJsonl:
    def test_serializes_single_row(self):
        rows = [{"query": "q1", "gold_ids": ["a"]}]
        text = to_jsonl(rows)
        assert json.loads(text) == rows[0]

    def test_serializes_multiple_rows(self):
        rows = [{"query": "q1"}, {"query": "q2"}]
        text = to_jsonl(rows)
        assert [json.loads(line) for line in text.split("\n")] == rows


# ---------------------------------------------------------------------------
# BenchmarkRunner
# ---------------------------------------------------------------------------
from geomemory.eval.runner import BenchmarkRunner


class TestBenchmarkRunner:
    def _make_workspace(self, search_results=None, ask_result=None):
        ws = mock.MagicMock()
        ws.search.return_value = search_results or mock.MagicMock(hits=[])
        ws.ask.return_value = ask_result or mock.MagicMock(
            sources=[], text="answer", abstained=False, citations=[]
        )
        return ws

    def _make_item(self, query="q", gold_ids=None, reference_answer="", expected_abstain=False):
        return BenchmarkItem(
            query=query,
            gold_ids=gold_ids or [],
            reference_answer=reference_answer,
            expected_abstain=expected_abstain,
        )

    def _make_benchmark(self, items):
        bench = mock.MagicMock()
        bench.name = "test"
        bench.__iter__ = lambda self: iter(items)
        bench.__len__ = lambda self: len(items)
        return bench

    def test_run_aggregates_retrieval_metrics(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a", "b"]}) + "\n"
        )
        ws = self._make_workspace(
            search_results=mock.MagicMock(
                hits=[mock.MagicMock(id="a"), mock.MagicMock(id="c")]
            )
        )
        runner = BenchmarkRunner(ws)
        result = runner.run(str(bench_path))
        assert "retrieval" in result.metrics
        assert "recall@10" in result.metrics["retrieval"]

    def test_run_aggregates_qa_metrics(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({
                "query": "q1",
                "reference_answer": "ref",
                "gold_ids": ["a"],
            }) + "\n"
        )
        ws = self._make_workspace(
            ask_result=mock.MagicMock(
                sources=[mock.MagicMock(id="a")],
                text="ans",
                abstained=False,
                citations=[],
            )
        )
        runner = BenchmarkRunner(ws)
        result = runner.run(str(bench_path))
        assert "qa" in result.metrics
        assert "abstention_accuracy" in result.metrics["qa"]

    def test_run_includes_latency(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
        )
        ws = self._make_workspace()
        runner = BenchmarkRunner(ws)
        result = runner.run(str(bench_path))
        assert "latency_ms" in result.metrics
        assert "retrieval_avg" in result.metrics["latency_ms"]

    def test_run_with_config_string(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
        )
        ws = self._make_workspace()
        runner = BenchmarkRunner(ws)
        config_json = json.dumps({"mode": "dense", "top_k_values": [5]})
        result = runner.run(str(bench_path), config=config_json)
        assert result.config.mode == "dense"
        assert result.config.top_k_values == [5]

    def test_run_with_config_file(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
        )
        cfg_path = tmp_path / "cfg.json"
        cfg_path.write_text(json.dumps({"mode": "hybrid", "top_k_values": [3, 5]}))
        ws = self._make_workspace()
        runner = BenchmarkRunner(ws)
        result = runner.run(str(bench_path), config=str(cfg_path))
        assert result.config.mode == "hybrid"
        assert result.config.top_k_values == [3, 5]

    def test_empty_top_k_raises(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
        )
        ws = self._make_workspace()
        runner = BenchmarkRunner(ws)
        with pytest.raises(ValueError, match="top_k_values must not be empty"):
            runner.run(str(bench_path), config=json.dumps({"top_k_values": []}))

    def test_missing_config_file_raises(self, tmp_path: Path):
        bench_path = tmp_path / "bench.jsonl"
        bench_path.write_text(
            json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n"
        )
        ws = self._make_workspace()
        runner = BenchmarkRunner(ws)
        with pytest.raises(FileNotFoundError):
            runner.run(str(bench_path), config="/nonexistent/cfg.json")


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------
from geomemory.eval.reporter import json_report, markdown_report


class TestJsonReport:
    def test_basic(self):
        report = json_report("bench1", {"retrieval": {"recall@10": 0.9}})
        data = json.loads(report)
        assert data["name"] == "bench1"
        assert data["metrics"]["retrieval"]["recall@10"] == pytest.approx(0.9)

    def test_empty_metrics(self):
        report = json_report("bench1", {})
        data = json.loads(report)
        assert data["metrics"] == {}


class TestMarkdownReport:
    def test_basic_structure(self):
        report = markdown_report("bench1", {"retrieval": {"recall@10": 0.9}})
        assert "# Benchmark: bench1" in report
        assert "| recall@10 | 0.900 |" in report

    def test_empty_groups_skipped(self):
        report = markdown_report("bench1", {"empty_group": {}})
        assert "# Benchmark: bench1" in report
        # No table rows for empty group
        assert "empty_group" not in report or "|" not in report.split("empty_group")[-1]

    def test_rounds_to_three_decimals(self):
        report = markdown_report("b", {"g": {"m": 0.12345}})
        assert "0.123" in report

    def test_trailing_newline(self):
        report = markdown_report("b", {"g": {"m": 1.0}})
        assert report.endswith("\n")
