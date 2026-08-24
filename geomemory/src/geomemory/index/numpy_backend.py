"""NumpyBackend — pure-numpy fallback retrieval backend.

This backend works fully offline without txtai or llama.cpp. It computes a
character n-gram TF representation of query and documents, then uses cosine
similarity for ranking. It satisfies the ``RetrievalBackend`` protocol and is
used automatically when no embedding model is loaded.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

import numpy as np

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest

_NGRAM = 3
_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


class NumpyBackend:
    """In-memory n-gram TF backend backed by the SQLite segment table.

    Vectors are lazily built from segment text on demand, so no model files
    or persistent index directories are required.
    """

    space_id = "text.numpy.v1"

    def __init__(self, records: list[IndexRecord] | None = None) -> None:
        self._records: list[IndexRecord] = []
        self._matrix: np.ndarray | None = None
        self._terms: list[str] = []
        if records:
            self.upsert(records)

    # ── Protocol implementation ──────────────────────────────────────────────

    def upsert(self, records: list[IndexRecord]) -> None:
        """Insert or replace records, invalidating the cached matrix."""
        by_id = {r.id: r for r in self._records}
        for record in records:
            by_id[record.id] = record
        self._records = list(by_id.values())
        self._matrix = None

    def delete(self, ids: list[str]) -> None:
        """Remove records by id."""
        self._records = [r for r in self._records if r.id not in set(ids)]
        self._matrix = None

    def count(self) -> int:
        """Return the number of indexed records."""
        return len(self._records)

    def rebuild(self, manifest: IndexManifest) -> None:
        """Rebuild from SQLite is handled by :meth:`from_database`."""
        raise NotImplementedError("Use NumpyBackend.from_database to rebuild")

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Rank records by cosine similarity of n-gram TF vectors."""
        if not self._records:
            return []
        matrix, terms = self._build()
        query_tf = self._tf(request.query, terms)
        norms = np.linalg.norm(matrix, axis=1)
        safe_norms = np.where(norms == 0, 1.0, norms)
        scores = (matrix @ query_tf) / safe_norms / (np.linalg.norm(query_tf) or 1.0)
        order = np.argsort(-scores)[: request.top_k]
        hits: list[SearchHit] = []
        for idx in order:
            score = float(scores[idx])
            if score <= 0:
                continue
            record = self._records[int(idx)]
            hits.append(
                SearchHit(
                    id=record.id,
                    dense_score=score,
                    text=record.text,
                    locator=record.metadata.get("locator", {}),
                    metadata=record.metadata,
                )
            )
        return hits[: request.top_k]

    # ── Vector construction ─────────────────────────────────────────────────

    def _build(self) -> tuple[np.ndarray, list[str]]:
        """Build the term-by-document TF matrix (cached)."""
        if self._matrix is not None and self._terms:
            return self._matrix, self._terms
        vocab: set[str] = set()
        for record in self._records:
            vocab.update(self._tokenize(record.text))
        terms = sorted(vocab)
        matrix = np.zeros((len(self._records), len(terms)), dtype=np.float32)
        for i, record in enumerate(self._records):
            counts = Counter(self._tokenize(record.text))
            for term, count in counts.items():
                if term in vocab:
                    matrix[i, terms.index(term)] = count
        self._matrix = matrix
        self._terms = terms
        return matrix, terms

    def _tf(self, text: str, terms: list[str]) -> np.ndarray:
        counts = Counter(self._tokenize(text))
        vec = np.zeros(len(terms), dtype=np.float32)
        for term, count in counts.items():
            if term in terms:
                vec[terms.index(term)] = count
        return vec

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize to lowercase, then produce character n-grams."""
        words = _TOKEN_RE.findall(text.lower())
        tokens: list[str] = []
        for word in words:
            if len(word) < _NGRAM:
                tokens.append(word)
                continue
            tokens.extend(word[i : i + _NGRAM] for i in range(len(word) - _NGRAM + 1))
        return tokens

    # ── SQLite construction ──────────────────────────────────────────────────

    @classmethod
    def from_database(
        cls, conn: sqlite3.Connection, collections: list[str] | None = None
    ) -> NumpyBackend:
        """Load all segments from a workspace database into a backend.

        When ``collections`` is given, only segments belonging to those
        collections are loaded.
        """
        sql = (
            "SELECT s.id, s.text, s.locator, s.revision_id, s.segment_type, s.metadata "
            "FROM segment s "
            "JOIN asset_revision r ON r.id = s.revision_id "
            "JOIN asset a ON a.id = r.asset_id "
        )
        params: list[str] = []
        if collections:
            placeholders = ",".join("?" for _ in collections)
            sql += f"WHERE a.collection_id IN ({placeholders}) "
            params.extend(collections)
        sql += "ORDER BY s.created_at"
        rows = conn.execute(sql, params).fetchall()
        records: list[IndexRecord] = []
        for r in rows:
            try:
                locator = json.loads(r["locator"]) if r["locator"] else {}
            except (json.JSONDecodeError, TypeError):
                locator = {}
            try:
                segment_meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                segment_meta = {}
            records.append(
                IndexRecord(
                    id=r["id"],
                    text=r["text"],
                    space_id=cls.space_id,
                    metadata={
                        "locator": locator,
                        "revision_id": r["revision_id"],
                        "segment_type": r["segment_type"],
                        **segment_meta,
                    },
                )
            )
        return cls(records)