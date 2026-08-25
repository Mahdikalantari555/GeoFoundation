"""Segment repository with FTS5 support."""

from __future__ import annotations

from geomemory.core.models import Segment
from geomemory.storage.repositories.base import BaseRepository


class SegmentRepository(BaseRepository[Segment]):
    """CRUD for segments, including FTS5 full-text search."""

    table = "segment"
    model_cls = Segment
    json_columns = ("locator", "neighbor_ids", "metadata")

    def get_by_revision(self, revision_id: str) -> list[Segment]:
        """Return all segments for a revision, in insertion order."""
        rows = self.conn.execute(
            "SELECT * FROM segment WHERE revision_id = ? ORDER BY created_at", (revision_id,)
        ).fetchall()
        return [self._load(r) for r in rows]

    def get_by_asset(self, asset_id: str) -> list[Segment]:
        """Return all segments belonging to an asset (via its revisions)."""
        rows = self.conn.execute(
            "SELECT s.* FROM segment s "
            "JOIN asset_revision r ON r.id = s.revision_id "
            "WHERE r.asset_id = ? ORDER BY s.created_at",
            (asset_id,),
        ).fetchall()
        return [self._load(r) for r in rows]

    def fts_search(self, query: str, *, top_k: int = 20) -> list[Segment]:
        """Full-text search over segment text using FTS5."""
        fts_query = " OR ".join(query.split()) or query
        rows = self.conn.execute(
            "SELECT s.* FROM segments_fts JOIN segment s ON s.rowid = segments_fts.rowid "
            "WHERE segments_fts MATCH ? ORDER BY bm25(segments_fts) LIMIT ?",
            (fts_query, top_k),
        ).fetchall()
        return [self._load(r) for r in rows]

    def count_by_revision(self, revision_id: str) -> int:
        """Return the number of segments for a revision."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM segment WHERE revision_id = ?", (revision_id,)
        ).fetchone()
        return int(row["c"]) if row is not None else 0