"""CandidateMemory repository helpers."""

from __future__ import annotations

import json
import sqlite3

from geomemory.core.models import CandidateMemory, utc_now


def _row_to_cm(row: sqlite3.Row) -> CandidateMemory:
    data = dict(row)
    for k in ("source_feedback_ids", "audit_trail"):
        if isinstance(data.get(k), str):
            try:
                data[k] = json.loads(data[k])
            except Exception:
                data[k] = []
    return CandidateMemory(**data)


class CandidateMemoryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, cm: CandidateMemory) -> CandidateMemory:
        self.conn.execute(
            "INSERT INTO candidate_memory (id, content, memory_type, source_feedback_ids, confidence_score, state, author, audit_trail, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                cm.id,
                cm.content,
                cm.memory_type,
                json.dumps(cm.source_feedback_ids),
                cm.confidence_score,
                cm.state,
                cm.author,
                json.dumps(cm.audit_trail),
                cm.created_at,
                cm.updated_at,
            ),
        )
        self.conn.commit()
        return cm

    def get(self, cm_id: str) -> CandidateMemory | None:
        row = self.conn.execute("SELECT * FROM candidate_memory WHERE id=?", (cm_id,)).fetchone()
        return _row_to_cm(row) if row else None

    def list(self, state: str | None = None) -> list[CandidateMemory]:
        if state:
            rows = self.conn.execute("SELECT * FROM candidate_memory WHERE state=? ORDER BY updated_at DESC", (state,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM candidate_memory ORDER BY updated_at DESC").fetchall()
        return [_row_to_cm(r) for r in rows]

    def promote(self, cm_id: str, new_state: str, reviewer_id: str | None, note: str | None, *, allow_regression: bool = False) -> CandidateMemory | None:
        cm = self.get(cm_id)
        if not cm:
            return None
        # validate transition: proposed->supported->verified|rejected, etc.
        valid = {
            "proposed": {"supported", "rejected"},
            "supported": {"verified", "rejected"},
            "verified": {"rejected"},
            "rejected": set(),
        }
        if new_state not in valid.get(cm.state, set()) and new_state != cm.state:
            # allow direct to rejected from any non-rejected
            if new_state == "rejected" and cm.state != "rejected":
                pass
            elif allow_regression:
                pass  # score-driven backward transition
            elif new_state != cm.state:
                raise ValueError(f"Invalid transition {cm.state} -> {new_state}")
        audit = list(cm.audit_trail)
        audit.append({"action": "promote", "to_state": new_state, "reviewer_id": reviewer_id, "note": note, "timestamp": utc_now()})
        updated_at = utc_now()
        self.conn.execute(
            "UPDATE candidate_memory SET state=?, audit_trail=?, updated_at=? WHERE id=?",
            (new_state, json.dumps(audit), updated_at, cm_id),
        )
        self.conn.commit()
        return self.get(cm_id)

    def update_score(self, cm_id: str, score: float) -> None:
        self.conn.execute("UPDATE candidate_memory SET confidence_score=?, updated_at=? WHERE id=?", (score, utc_now(), cm_id))
        self.conn.commit()

    def search(self, query: str, min_score: float = 0) -> list[CandidateMemory]:
        rows = self.conn.execute("SELECT * FROM candidate_memory WHERE confidence_score >= ? AND content LIKE ? ORDER BY confidence_score DESC", (min_score, f"%{query}%")).fetchall()
        return [_row_to_cm(r) for r in rows]
