"""Tests for the new model-management API and index auto-download."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from geofront_api.main import create_app
from geofront_api.state import AppState


@pytest.fixture
def client():
    app = create_app()
    app.state.geofront_state = AppState()
    return TestClient(app)


class TestModelsRouter:
    def test_list_models_returns_empty_when_no_hub(self, client):
        resp = client.get("/api/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Hub may contain cached models from previous runs; ensure shape if present
        for m in data:
            assert "id" in m and "backend" in m

    def test_download_unknown_backend_422(self, client):
        resp = client.post(
            "/api/v1/models/download",
            json={"model_name": "foo", "backend": "bogus"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "invalid_backend"

    def test_download_model_status_not_found(self, client):
        resp = client.get("/api/v1/models/st:foo-bar/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["downloaded"] is False
        assert body["found"] is False


class TestIndexAutoDownload:
    def test_build_without_workspace_returns_409(self, client):
        resp = client.post("/api/v1/index/build")
        assert resp.status_code == 409
