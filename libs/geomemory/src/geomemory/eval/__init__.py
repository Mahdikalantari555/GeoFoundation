"""Evaluation modules: benchmark definitions, metrics, runner, reports."""

from __future__ import annotations

from geomemory.eval.benchmark import Benchmark, BenchmarkItem, load_benchmark
from geomemory.eval.reporter import json_report, markdown_report
from geomemory.eval.retrieval_metrics import mrr_at_k, ndcg_at_k, precision_at_k, recall_at_k
from geomemory.eval.runner import BenchmarkRunner
from geomemory.eval.qa_metrics import (
    abstention_accuracy,
    citation_correctness,
    faithfulness_proxy,
)

__all__ = [
    "Benchmark",
    "BenchmarkItem",
    "BenchmarkRunner",
    "abstention_accuracy",
    "citation_correctness",
    "faithfulness_proxy",
    "json_report",
    "load_benchmark",
    "markdown_report",
    "mrr_at_k",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]