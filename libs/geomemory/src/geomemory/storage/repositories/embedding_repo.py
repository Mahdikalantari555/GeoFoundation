"""EmbeddingRecord repository."""

from __future__ import annotations

import sqlite3

from geomemory.core.models import EmbeddingRecord


class EmbeddingRepository:
    """CRUD for embedding records (composite primary key)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, record: EmbeddingRecord) -> EmbeddingRecord:
        """Insert or replace an embedding record."""
        self.conn.execute(
            "INSERT OR REPLACE INTO embedding_record "
            "(target_id, target_type, space_id, model_id, dimension, checksum, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.target_id,
                record.target_type,
                record.space_id,
                record.model_id,
                record.dimension,
                record.checksum,
                record.created_at,
            ),
        )
        self.conn.commit()
        return record

    def get(self, target_id: str, target_type: str, space_id: str) -> EmbeddingRecord | None:
        """Fetch a record by its composite key."""
        row = self.conn.execute(
            "SELECT * FROM embedding_record WHERE target_id = ? AND target_type = ? AND space_id = ?",
            (target_id, target_type, space_id),
        ).fetchone()
        return EmbeddingRecord(**dict(row)) if row is not None else None

    def get_by_space(self, space_id: str) -> list[EmbeddingRecord]:
        """Return all records in an embedding space."""
        rows = self.conn.execute(
            "SELECT * FROM embedding_record WHERE space_id = ? ORDER BY created_at", (space_id,)
        ).fetchall()
        return [EmbeddingRecord(**dict(r)) for r in rows]

    def get_by_target(self, target_id: str) -> list[EmbeddingRecord]:
        """Return all records for a target entity."""
        rows = self.conn.execute(
            "SELECT * FROM embedding_record WHERE target_id = ? ORDER BY created_at", (target_id,)
        ).fetchall()
        return [EmbeddingRecord(**dict(r)) for r in rows]

    def delete(self, target_id: str, target_type: str, space_id: str) -> bool:
        """Delete a record. Returns True if a row was deleted."""
        cur = self.conn.execute(
            "DELETE FROM embedding_record WHERE target_id = ? AND target_type = ? AND space_id = ?",
            (target_id, target_type, space_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_by_space(self, space_id: str) -> int:
        """Delete all records in a space. Returns the number deleted."""
        cur = self.conn.execute(
            "DELETE FROM embedding_record WHERE space_id = ?", (space_id,)
        )
        self.conn.commit()
        return cur.rowcount

    def count(self) -> int:
        """Return the total number of records."""
        row = self.conn.execute("SELECT COUNT(*) AS c FROM embedding_record").fetchone()
        return int(row["c"]) if row is not None else 0
