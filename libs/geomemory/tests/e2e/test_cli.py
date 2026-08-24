"""End-to-end tests for the CLI."""

from __future__ import annotations

import json

from click.testing import CliRunner

from geomemory.cli.main import cli


class TestCliLifecycle:
    def test_version(self):
        result = CliRunner().invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output

    def test_init(self, tmp_path):
        ws = tmp_path / "ws"
        result = CliRunner().invoke(cli, ["init", str(ws)])
        assert result.exit_code == 0
        assert "Created workspace" in result.output
        assert (ws / "geomemory.db").is_file()

    def test_open_missing_fails(self, tmp_path):
        result = CliRunner().invoke(cli, ["search", "x", "-w", str(tmp_path / "nope")])
        assert result.exit_code != 0


class TestCliSearch:
    def _seed(self, tmp_path, sample_markdown):
        from geomemory import GeoMemory

        ws = tmp_path / "ws"
        CliRunner().invoke(cli, ["init", str(ws)])
        gm = GeoMemory.open(ws)
        try:
            col = gm.create_collection("docs")
            collection_id = col.id
        finally:
            gm.close()
        CliRunner().invoke(cli, ["ingest", str(sample_markdown), "-w", str(ws), "-c", collection_id])
        return ws

    def test_ingest_then_search(self, tmp_path, sample_markdown):
        ws = self._seed(tmp_path, sample_markdown)
        result = CliRunner().invoke(cli, ["search", "NDVI crop", "-w", str(ws)])
        assert result.exit_code == 0
        assert "Hits:" in result.output

    def test_search_json_output(self, tmp_path, sample_markdown):
        ws = self._seed(tmp_path, sample_markdown)
        result = CliRunner().invoke(cli, ["search", "NDVI", "-w", str(ws), "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "hits" in payload
        assert payload["query"] == "NDVI"

    def test_search_markdown_output(self, tmp_path, sample_markdown):
        ws = self._seed(tmp_path, sample_markdown)
        result = CliRunner().invoke(cli, ["search", "NDVI", "-w", str(ws), "--format", "markdown"])
        assert result.exit_code == 0
        assert "| # |" in result.output or "Query:" in result.output

    def test_feedback_export_empty(self, tmp_path, sample_markdown):
        ws = self._seed(tmp_path, sample_markdown)
        result = CliRunner().invoke(cli, ["feedback", "export", "--type", "qa_eval", "--output", str(tmp_path), "-w", str(ws)])
        assert result.exit_code != 0  # no accepted examples yet

    def test_feedback_review_empty(self, tmp_path):
        ws = tmp_path / "ws"
        CliRunner().invoke(cli, ["init", str(ws)])
        result = CliRunner().invoke(cli, ["feedback", "review", "-w", str(ws)])
        assert result.exit_code == 0
        assert "empty" in result.output

    def test_doctor(self, tmp_path):
        result = CliRunner().invoke(cli, ["doctor", "--workspace", str(tmp_path)])
        assert result.exit_code == 0
        assert "environment" in result.output or "core" in result.output

    def test_app_help(self):
        result = CliRunner().invoke(cli, ["app", "--help"])
        assert result.exit_code == 0
        assert "Launch" in result.output
