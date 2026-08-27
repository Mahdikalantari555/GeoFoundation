"""Agent conversations route: list and retrieve conversations."""

from __future__ import annotations

from fastapi import APIRouter

from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/conversations", tags=["agent"])


@router.get("")
async def list_conversations() -> dict[str, object]:
    """List all agent conversations."""
    service = get_agent_service()
    conversations = service.store.list_conversations()
    return {"conversations": conversations}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, object]:
    """Get a conversation with its turns and tool runs."""
    service = get_agent_service()
    store = service.store

    # Verify conversation exists
    convs = store.list_conversations()
    conv = next((c for c in convs if c["id"] == conversation_id), None)
    if conv is None:
        from ...errors import GeoFrontError
        raise GeoFrontError(
            code="conversation_not_found",
            message=f"Conversation not found: {conversation_id}",
            status_code=404,
        )

    turns = store.turns(conversation_id)
    tool_runs = [
        dict(r)
        for r in store.conn.execute(
            "SELECT id, tool, args_json, status, latency_ms, error, from_cache, created_at "
            "FROM tool_run WHERE conversation_id=? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
    ]

    return {
        "conversation": conv,
        "turns": turns,
        "tool_runs": tool_runs,
    }
