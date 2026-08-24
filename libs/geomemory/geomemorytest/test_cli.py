"""CLI command tests using click.testing.CliRunner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from geomemory.cli.main import cli as geomemory_cli


# ===========================================================================
# Helpers
# ===========================================================================


@pytest.fixture()
def runner():
    return CliRunner()


# ===========================================================================
# Init
# ===========================================================================


class TestInit:
    def test_init_creates_workspace(self, runner, tmp_path):
        target = tmp_path / "ws"
        result = runner.invoke(geomemory_cli, ["init", str(target)])
        assert result.exit_code == 0
        assert target.is_dir()
        assert (target / ".geomemory").is_file()
        assert "Created workspace" in result.output

    def test_init_with_name(self, runner, tmp_path):
        target = tmp_path / "ws2"
        result = runner.invoke(geomemory_cli, ["init", str(target), "--name", "My WS"])
        assert result.exit_code == 0
        assert "My WS" in result.output

    def test_init_with_language(self, runner, tmp_path):
        target = tmp_path / "ws3"
        result = runner.invoke(geomemory_cli, ["init", str(target), "--language", "fa"])
        assert result.exit_code == 0
        # Language is stored in config; just verify init succeeds.
        assert "Created workspace" in result.output

    def test_init_no_offline(self, runner, tmp_path):
        target = tmp_path / "ws4"
        result = runner.invoke(geomemory_cli, ["init", str(target), "--no-offline"])
        assert result.exit_code == 0
        assert "False" in result.output


# ===========================================================================
# Search
# ===========================================================================


class TestSearch:
    def test_search_json_output(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        # Create a minimal workspace marker
        (ws_root / ".geomemory").write_text("")

        fake_result = mock.MagicMock()
        fake_result.query = "test query"
        fake_result.mode = "hybrid"
        fake_result.total_hits = 2
        fake_result.latency_ms = 10
        fake_result.retrieval_run_id = "run-123"
        fake_result.hits = [
            mock.MagicMock(id="seg1", score=0.9, sparse_score=0.8, dense_score=0.9, text="hello world", locator="p1", metadata={"segment_type": "text"}),
            mock.MagicMock(id="seg2", score=0.7, sparse_score=0.6, dense_score=0.7, text="goodbye world", locator="p2", metadata={"segment_type": "text"}),
        ]

        with mock.patch("geomemory.cli.commands.search.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.search.return_value = fake_result
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["search", "test query", "--workspace", str(ws_root), "--format", "json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["query"] == "test query"
        assert payload["total_hits"] == 2
        assert len(payload["hits"]) == 2
        assert payload["hits"][0]["id"] == "seg1"

    def test_search_table_output(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        fake_result = mock.MagicMock()
        fake_result.query = "q"
        fake_result.mode = "hybrid"
        fake_result.total_hits = 1
        fake_result.latency_ms = 5
        fake_result.retrieval_run_id = "run-1"
        fake_result.hits = [
            mock.MagicMock(id="s1", score=0.95, sparse_score=None, dense_score=0.95, text="some text here", locator="loc1", metadata={"segment_type": "text"}),
        ]

        with mock.patch("geomemory.cli.commands.search.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.search.return_value = fake_result
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["search", "q", "--workspace", str(ws_root)])

        assert result.exit_code == 0
        assert "Query: q" in result.output
        assert "Hits: 1" in result.output


# ===========================================================================
# Chat (replaces ask in CLI)
# ===========================================================================


class TestChat:
    def test_chat_command_exists(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        # chat is interactive; just verify it starts without error when
        # mocked. The command reads from stdin, so we close it immediately.
        fake_result = mock.MagicMock()
        fake_result.text = "42"
        fake_result.abstained = False
        fake_result.citations = []
        fake_result.abstention_reason = ""

        with mock.patch("geomemory.cli.commands.chat.GeoMemory") as mock_gm, \
             mock.patch("click.termui.prompt", side_effect=EOFError):
            mock_ws = mock.MagicMock()
            mock_ws.ask.return_value = fake_result
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["chat", "--workspace", str(ws_root)], input="")

        # EOF from empty input causes exit; verify command was recognized.
        assert result.exit_code in (0, 1)  # 1 on EOF from click.prompt


# ===========================================================================
# Doctor
# ===========================================================================


class TestDoctor:
    def test_doctor_environment_check(self, runner):
        result = runner.invoke(geomemory_cli, ["doctor", "--workspace", "/nonexistent"])
        assert result.exit_code == 0
        assert "GeoMemory environment" in result.output
        assert "Python:" in result.output

    def test_doctor_reports_core_deps(self, runner):
        result = runner.invoke(geomemory_cli, ["doctor", "--workspace", "/nonexistent"])
        assert "pydantic" in result.output
        assert "numpy" in result.output

    def test_doctor_workspace_missing(self, runner):
        result = runner.invoke(geomemory_cli, ["doctor", "--workspace", "/nonexistent"])
        assert "FAILED" in result.output


# ===========================================================================
# Eval
# ===========================================================================


class TestEval:
    def test_eval_run(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        bench_file = tmp_path / "bench.jsonl"
        bench_file.write_text(json.dumps({"query": "q1", "gold_ids": ["a"]}) + "\n")

        fake_result = mock.MagicMock()
        fake_result.name = "bench"
        fake_result.metrics = {"retrieval": {"recall@10": 0.9}, "qa": {}}

        with mock.patch("geomemory.cli.commands.eval_cmd.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.run_benchmark.return_value = fake_result
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["eval", "run", str(bench_file), "--workspace", str(ws_root)])

        assert result.exit_code == 0
        assert "Benchmark: bench" in result.output
        assert "recall@10" in result.output


# ===========================================================================
# Feedback
# ===========================================================================


class TestFeedback:
    def test_feedback_export(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        with mock.patch("geomemory.cli.commands.feedback.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.export_dataset.return_value = str(tmp_path / "dataset.jsonl")
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, [
                "feedback", "export",
                "--workspace", str(ws_root),
                "--type", "rag_eval",
                "--output", str(tmp_path),
            ])

        assert result.exit_code == 0
        assert "Exported dataset" in result.output

    def test_feedback_review_empty(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        with mock.patch("geomemory.cli.commands.feedback.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.get_review_queue.return_value = []
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["feedback", "review", "--workspace", str(ws_root)])

        assert result.exit_code == 0
        assert "Review queue is empty" in result.output


# ===========================================================================
# Index
# ===========================================================================


class TestIndex:
    def test_index_build(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        with mock.patch("geomemory.cli.commands.index.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.build_index.return_value = None
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["index", "build", "--workspace", str(ws_root)])

        assert result.exit_code == 0
        assert "Built index" in result.output

    def test_index_rebuild(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        with mock.patch("geomemory.cli.commands.index.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.rebuild_index.return_value = None
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, ["index", "rebuild", "--workspace", str(ws_root)])

        assert result.exit_code == 0
        assert "Rebuilt index" in result.output


# ===========================================================================
# Ingest
# ===========================================================================


class TestIngest:
    def test_ingest_file(self, runner, tmp_path):
        ws_root = tmp_path / "ws"
        ws_root.mkdir()
        (ws_root / ".geomemory").write_text("")

        src_file = tmp_path / "doc.md"
        src_file.write_text("# Hello world")

        fake_job = mock.MagicMock()
        fake_job.id = "job-1"
        fake_job.state = "completed"
        fake_job.result = {"segments": 1}

        with mock.patch("geomemory.cli.commands.ingest.GeoMemory") as mock_gm:
            mock_ws = mock.MagicMock()
            mock_ws.ingest.return_value = fake_job
            mock_ws.close.return_value = None
            mock_gm.open.return_value = mock_ws

            result = runner.invoke(geomemory_cli, [
                "ingest", str(src_file),
                "--workspace", str(ws_root),
                "--collection", "default",
            ])

        assert result.exit_code == 0
        assert "job-1" in result.output
