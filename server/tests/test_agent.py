"""Tests for agent routes: chat SSE, conversations, tools, playbooks, files."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from geofront_api.main import create_app
from geofront_api.services.agent import reset_agent_service
from geofront_api.state import reset_state


@pytest.fixture()
def client() -> TestClient:
    reset_state()
    reset_agent_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_state()
    reset_agent_service()


@pytest.fixture()
def open_ws(client: TestClient, tmp_path: pytest.PathFactory) -> None:
    ws_path = str(tmp_path / "ws")
    resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "Agent WS"})
    assert resp.status_code == 201


class TestAgentTools:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent/tools")
        assert resp.status_code == 409

    def test_list_tools(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert "tools" in body
        assert len(body["tools"]) > 0
        names = [t["name"] for t in body["tools"]]
        assert "geo_search" in names
        assert "geo_ingest" in names


class TestAgentConversations:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent/conversations")
        assert resp.status_code == 409

    def test_list_conversations_empty(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["conversations"] == []

    def test_get_conversation_not_found(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/conversations/nonexistent")
        assert resp.status_code == 404


class TestAgentPlaybooks:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent/playbooks")
        assert resp.status_code == 409

    def test_list_playbooks_empty(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/playbooks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["playbooks"] == []

    def test_get_playbook_not_found(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/playbooks/nonexistent")
        assert resp.status_code == 404


class TestAgentFiles:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agent/files/list")
        assert resp.status_code == 409

    def test_list_files_empty(self, client: TestClient, open_ws: None) -> None:
        resp = client.get("/api/v1/agent/files/list")
        assert resp.status_code == 200
        body = resp.json()
        assert "files" in body


class TestAgentChat:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/agent/chat", json={"message": "hello"})
        assert resp.status_code == 409
