"""ProposalEngine — generate KnowledgeChangeProposal from verified candidates."""

from __future__ import annotations

import json
import sqlite3

from geomemory.core.models import CandidateMemory, KnowledgeChangeProposal, utc_now


class ProposalEngine:
    def __init__(self, conn: sqlite3.Connection, *, max_per_session: int = 5) -> None:
        self.conn = conn
        self.max_per_session = max_per_session
        self._generated = 0

    def generate(self, candidate: CandidateMemory) -> KnowledgeChangeProposal | None:
        if candidate.state != "verified":
            return None
        if self._generated >= self.max_per_session:
            return None
        # Determine type from memory_type/content heuristic
        ptype = "graph_relation"
        if candidate.memory_type == "preference":
            ptype = "metadata_update"
        elif "entity" in candidate.content.lower()[:100]:
            ptype = "entity_create"
        proposal = KnowledgeChangeProposal(
            proposal_type=ptype,  # type: ignore[arg-type]
            diff={"original": None, "proposed": candidate.content},
            source_candidate_ids=[candidate.id],
            confidence=candidate.confidence_score,
            status="pending",
        )
        self.conn.execute(
            "INSERT INTO knowledge_change_proposal (id, proposal_type, diff, source_candidate_ids, confidence, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (proposal.id, proposal.proposal_type, json.dumps(proposal.diff), json.dumps(proposal.source_candidate_ids), proposal.confidence, proposal.status, proposal.created_at),
        )
        self.conn.commit()
        self._generated += 1
        return proposal

    def list(self, status: str | None = None) -> list[KnowledgeChangeProposal]:
        if status:
            rows = self.conn.execute("SELECT * FROM knowledge_change_proposal WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM knowledge_change_proposal ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("diff", "source_candidate_ids"):
                if isinstance(d.get(k), str):
                    try:
                        d[k] = json.loads(d[k])
                    except Exception:
                        d[k] = [] if k != "diff" else {}
            out.append(KnowledgeChangeProposal(**d))
        return out

    def review(self, proposal_id: str, approve: bool, reviewer_id: str | None, note: str | None) -> KnowledgeChangeProposal | None:
        row = self.conn.execute("SELECT * FROM knowledge_change_proposal WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            return None
        status = "approved" if approve else "rejected"
        reviewed_at = utc_now()
        self.conn.execute("UPDATE knowledge_change_proposal SET status=?, reviewed_at=?, reviewer_id=?, review_note=? WHERE id=?", (status, reviewed_at, reviewer_id, note, proposal_id))
        self.conn.commit()
        if approve:
            # Apply graph_relation to relation table if type matches
            d = dict(row)
            try:
                diff = json.loads(d["diff"]) if isinstance(d["diff"], str) else d["diff"]
            except Exception:
                diff = {}
            ptype = d.get("proposal_type")
            if ptype == "graph_relation":
                try:
                    proposed = diff.get("proposed") if isinstance(diff, dict) else None
                    # expected format "source -> predicate -> target" or store as relation with source/target placeholder
                    # For now insert a generic relation if content looks structured
                    if isinstance(proposed, str) and "->" in proposed:
                        parts = [p.strip() for p in proposed.split("->")]
                        if len(parts) >= 3:
                            self.conn.execute("INSERT OR IGNORE INTO relation (id, source_id, predicate, target_id, confidence, extractor, created_at) VALUES (?,?,?,?,?,?,?)", (f"rel_{proposal_id[:8]}", parts[0], parts[1], parts[2], 0.9, "proposal", reviewed_at))
                            self.conn.commit()
                except Exception:
                    pass
        # return updated
        row2 = self.conn.execute("SELECT * FROM knowledge_change_proposal WHERE id=?", (proposal_id,)).fetchone()
        if not row2:
            return None
        d2 = dict(row2)
        for k in ("diff", "source_candidate_ids"):
            if isinstance(d2.get(k), str):
                try:
                    d2[k] = json.loads(d2[k])
                except Exception:
                    d2[k] = [] if k != "diff" else {}
        return KnowledgeChangeProposal(**d2)
