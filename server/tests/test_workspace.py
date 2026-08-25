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
def ws_path(tmp_path: pytest.PathFactory) -> str:
    return str(tmp_path / "ws")


class TestWorkspaceLifecycle:
    def test_closed_initially(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspace")
        assert resp.status_code == 200
        assert resp.json() == {"status": "closed", "path": None, "settings": None}

    def test_create_open_close_roundtrip(self, client: TestClient, ws_path: str) -> None:
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "Test WS"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "open"
        assert body["settings"]["name"] == "Test WS"
        assert body["settings"]["offline"] is True

        # health reflects open workspace
        health = client.get("/health").json()
        assert health["workspace"]["status"] == "open"
        assert health["workspace"]["name"] == "Test WS"

        resp = client.post("/api/v1/workspace/close")
        assert resp.json() == {"status": "closed"}

        resp = client.get("/api/v1/workspace")
        assert resp.json()["status"] == "closed"

    def test_create_twice_conflicts(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_exists"

    def test_open_missing_404(self, client: TestClient, tmp_path: pytest.PathFactory) -> None:
        resp = client.post(
            "/api/v1/workspace/open", json={"path": str(tmp_path / "nope")}
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "workspace_not_found"

    def test_open_existing_workspace(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "First"})
        client.post("/api/v1/workspace/close")
        resp = client.post("/api/v1/workspace/open", json={"path": ws_path})
        assert resp.status_code == 200
        assert resp.json()["settings"]["name"] == "First"


class TestSettings:
    def test_stats_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspace/stats")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_update_settings(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put(
            "/api/v1/workspace/settings",
            json={"name": "Renamed", "batch_size": 32, "llm_provider": "api"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Renamed"
        assert body["batch_size"] == 32
        assert body["llm_provider"] == "api"

        # persisted across reopen
        client.post("/api/v1/workspace/close")
        client.post("/api/v1/workspace/open", json={"path": ws_path})
        resp = client.get("/api/v1/workspace")
        assert resp.json()["settings"]["name"] == "Renamed"

    def test_update_unknown_setting_rejected(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"nonsense": 1})
        assert resp.status_code == 422

    def test_update_invalid_language_rejected(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"language": "fr"})
        assert resp.status_code == 422

    def test_stats_shape(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.get("/api/v1/workspace/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


class TestSecrets:
    def test_settings_never_leak_qdrant_key(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        client.put("/api/v1/workspace/settings", json={"qdrant_api_key": "qdrant-secret"})
        # value may round-trip in settings (workspace-local secret), but the
        # LLM key (server env) must never appear
        import os

        os.environ["GEOMEMORY_LLM_API_KEY"] = "llm-secret-value"
        try:
            health = client.get("/health").text
            ws_resp = client.get("/api/v1/workspace").text
            assert "llm-secret-value" not in health
            assert "llm-secret-value" not in ws_resp
        finally:
            del os.environ["GEOMEMORY_LLM_API_KEY"]
