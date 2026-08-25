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


class TestHealth:
    def test_health_no_workspace(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["workspace"]["status"] == "closed"
        assert body["workspace"]["path"] is None
        assert body["llm"]["provider"] == "api"
        assert isinstance(body["llm"]["key_configured"], bool)

    def test_health_prefixed(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_health_reports_key_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GEOMEMORY_LLM_API_KEY", raising=False)
        resp = client.get("/health")
        assert resp.json()["llm"]["key_configured"] is False

        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "test-key")
        resp = client.get("/health")
        assert resp.json()["llm"]["key_configured"] is True

    def test_key_never_in_response(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "super-secret")
        resp = client.get("/health")
        assert "super-secret" not in resp.text


class TestErrorEnvelope:
    def test_unknown_route_uses_envelope(self, client: TestClient) -> None:
        resp = client.get("/api/v1/definitely-not-a-route")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"]
        assert body["error"]["message"]
