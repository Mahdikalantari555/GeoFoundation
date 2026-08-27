from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from geofront_api.main import create_app
from geofront_api.state import reset_state


@pytest.fixture()
def client() -> TestClient:
    reset_state()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_state()


@pytest.fixture()
def open_ws(client: TestClient, tmp_path: pytest.PathFactory) -> None:
    ws_path = str(tmp_path / "ws")
    resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "Ops WS"})
    assert resp.status_code == 201


class TestDoctor:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/doctor")
        assert resp.status_code == 409

    def test_diagnostics_report(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/doctor")
        assert resp.status_code == 200
        body = resp.json()
        assert "environment" in body
        assert "workspace" in body
        assert "workspace_open" in body
        assert body["environment"]["python_ok"] is True

    def test_llm_probe(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/doctor/llm")
        assert resp.status_code == 200
        assert "provider" in resp.json()


class TestIndex:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/index/build")
        assert resp.status_code == 409


class TestEval:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/eval/run", json={"benchmark_path": "/nope.jsonl"})
        assert resp.status_code == 409

    def test_missing_benchmark_404(self, client: TestClient, open_ws: None) -> None:
        resp = client.post("/api/v1/eval/run", json={"benchmark_path": "/nope.jsonl"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "eval_file_not_found"


class TestFeedbackExport:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/feedback/export", params={"task_type": "sft"})
        assert resp.status_code == 409

    def test_export_empty_404(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/feedback/export", params={"task_type": "sft"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "feedback_export_empty"
