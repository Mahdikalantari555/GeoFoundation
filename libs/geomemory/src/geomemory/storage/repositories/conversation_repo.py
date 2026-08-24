"""Conversation and turn repository."""

from __future__ import annotations

import json
import sqlite3

from geomemory.core.models import Conversation, Turn


class ConversationRepository:
    """CRUD for conversations."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, conversation: Conversation) -> Conversation:
        """Insert a conversation."""
        self.conn.execute(
            "INSERT INTO conversation (id, workspace_id, collection_scope, title, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                conversation.id,
                conversation.workspace_id,
                json.dumps(conversation.collection_scope),
                conversation.title,
                conversation.created_at,
                json.dumps(conversation.metadata),
            ),
        )
        self.conn.commit()
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        """Fetch a conversation by id."""
        row = self.conn.execute(
            "SELECT * FROM conversation WHERE id = ?", (conversation_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["collection_scope"] = json.loads(data["collection_scope"] or "[]")
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return Conversation(**data)

    def list_by_workspace(self, workspace_id: str) -> list[Conversation]:
        """Return all conversations in a workspace."""
        rows = self.conn.execute(
            "SELECT * FROM conversation WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,),
        ).fetchall()
        result = []
        for r in rows:
            data = dict(r)
            data["collection_scope"] = json.loads(data["collection_scope"] or "[]")
            data["metadata"] = json.loads(data["metadata"] or "{}")
            result.append(Conversation(**data))
        return result

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation (cascades to turns)."""
        cur = self.conn.execute("DELETE FROM conversation WHERE id = ?", (conversation_id,))
        self.conn.commit()
        return cur.rowcount > 0


class TurnRepository:
    """CRUD for turns."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, turn: Turn) -> Turn:
        """Insert a turn."""
        self.conn.execute(
            "INSERT INTO turn (id, conversation_id, role, content, created_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                turn.id,
                turn.conversation_id,
                turn.role,
                turn.content,
                turn.created_at,
                json.dumps(turn.metadata),
            ),
        )
        self.conn.commit()
        return turn

    def get(self, turn_id: str) -> Turn | None:
        """Fetch a turn by id."""
        row = self.conn.execute("SELECT * FROM turn WHERE id = ?", (turn_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return Turn(**data)

    def list_by_conversation(self, conversation_id: str) -> list[Turn]:
        """Return all turns in a conversation, in order."""
        rows = self.conn.execute(
            "SELECT * FROM turn WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
        result = []
        for r in rows:
            data = dict(r)
            data["metadata"] = json.loads(data["metadata"] or "{}")
            result.append(Turn(**data))
        return result