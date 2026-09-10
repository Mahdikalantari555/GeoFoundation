"""Tests for the POST /api/v1/ask/{turn_id}/suggest endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient
from geofront_api.state import get_state
from geomemory.core.models import Conversation, Turn, utc_now
from geomemory.storage.repositories.conversation_repo import (
    ConversationRepository,
    TurnRepository,
)


def _add_assistant_turn(client: TestClient) -> str:
    """Insert an assistant turn into the currently-open workspace and return its id."""
    ws = get_state().workspace
    conv = Conversation(workspace_id=ws._workspace_id(), title="test conv")
    ConversationRepository(ws.conn).create(conv)
    turn = Turn(
        conversation_id=conv.id,
        role="assistant",
        content="NDVI indicates vegetation health.",
        created_at=utc_now(),
    )
    TurnRepository(ws.conn).create(turn)
    return turn.id


class TestSuggestEndpoint:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/ask/any_turn_id/suggest", json={"content": "fixed answer"})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_missing_turn_returns_404(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/ask/nonexistent_turn/suggest", json={"content": "correction"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "turn_not_found"

    def test_empty_content_returns_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/ask/some_turn/suggest", json={"content": ""})
        assert resp.status_code == 422

    def test_missing_content_returns_422(self, client: TestClient, open_ws: dict) -> None:
        resp = client.post("/api/v1/ask/some_turn/suggest", json={})
        assert resp.status_code == 422

    def test_success_creates_candidate(self, client: TestClient, open_ws: dict) -> None:
        turn_id = _add_assistant_turn(client)
        resp = client.post(
            f"/api/v1/ask/{turn_id}/suggest",
            json={"content": "NDVI is a better indicator of plant stress."},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["content"] == "NDVI is a better indicator of plant stress."
        assert body["memory_type"] == "correction"
        assert body["state"] == "proposed"
        assert body["confidence_score"] == 5.0
        assert turn_id in body["source_feedback_ids"]

    def test_success_with_custom_memory_type(self, client: TestClient, open_ws: dict) -> None:
        turn_id = _add_assistant_turn(client)
        resp = client.post(
            f"/api/v1/ask/{turn_id}/suggest",
            json={"content": "annotated fact", "memory_type": "annotation"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["memory_type"] == "annotation"
        assert turn_id in body["source_feedback_ids"]
