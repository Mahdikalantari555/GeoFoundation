"""VectorBackend — persisted dense retrieval backend.

Stores precomputed embedding vectors (from any :class:`TextEmbedder`) on disk
as ``records.json`` + ``embeddings.npy`` under an index directory. Search is
cosine similarity against the query embedding produced by the same embedder.
This backend is fully offline and requires no torch or model files.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest
from geomemory.embeddings.normalization import l2_normalize

_RECORDS_FILENAME = "records.json"
_EMBEDDINGS_FILENAME = "embeddings.npy"


class VectorBackend:
    """Dense retrieval over persisted embedding vectors."""

    space_id = "text.hash.v1"

    def __init__(
        self,
        records: list[IndexRecord] | None = None,
        embeddings: np.ndarray | None = None,
        *,
        space_id: str | None = None,
    ) -> None:
        self._records: list[IndexRecord] = []
        self._embeddings: np.ndarray | None = None
        if space_id is not None:
            self.space_id = space_id
        if records:
            self.upsert(records, embeddings=embeddings)

    # ── Protocol implementation ──────────────────────────────────────────────

    def upsert(self, records: list[IndexRecord], *, embeddings: np.ndarray | None = None) -> None:
        """Insert or replace records, optionally with their embedding vectors."""
        if not records:
            return
        by_id = {r.id: r for r in self._records}
        for record in records:
            by_id[record.id] = record
        self._records = list(by_id.values())

        if embeddings is not None:
            if embeddings.shape[0] != len(records):
                raise ValueError(
                    f"embeddings rows ({embeddings.shape[0]}) must match records ({len(records)})"
                )
            # Rebuild the full matrix from the merged record order.
            matrix = np.zeros((len(self._records), embeddings.shape[1]), dtype=np.float32)
            index_of = {r.id: i for i, r in enumerate(self._records)}
            for record, vec in zip(records, embeddings, strict=False):
                matrix[index_of[record.id]] = vec
            self._embeddings = l2_normalize(matrix)
        else:
            # Embeddings not provided: fall back to per-record embedding field.
            matrix = np.zeros((len(self._records), self._infer_dimension()), dtype=np.float32)
            index_of = {r.id: i for i, r in enumerate(self._records)}
            for record in self._records:
                vec = record.embedding
                if vec is not None:
                    matrix[index_of[record.id]] = np.asarray(vec, dtype=np.float32)
            self._embeddings = l2_normalize(matrix)

    def delete(self, ids: list[str]) -> None:
        """Remove records by id."""
        removed = set(ids)
        original = self._records
        keep = [r for r in original if r.id not in removed]
        if len(keep) == len(original):
            return
        self._records = keep
        if self._embeddings is not None:
            keep_idx = [i for i, r in enumerate(original) if r.id not in removed]
            self._embeddings = self._embeddings[keep_idx]

    def count(self) -> int:
        """Return the number of indexed records."""
        return len(self._records)

    def rebuild(self, manifest: IndexManifest) -> None:
        """Rebuild is handled by the IndexService; not supported here."""
        raise NotImplementedError("Use IndexService.build to rebuild a VectorBackend")

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Rank records by cosine similarity of query embedding."""
        if not self._records or self._embeddings is None:
            return []
        query_vec = request.query_embedding
        if query_vec is None:
            return []
        q = l2_normalize(np.asarray(query_vec, dtype=np.float32).reshape(1, -1))
        scores = self._embeddings @ q.T
        order = np.argsort(-scores[:, 0])[: request.top_k]
        hits: list[SearchHit] = []
        for idx in order:
            score = float(scores[idx, 0])
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

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self, index_dir: str | Path) -> None:
        """Persist records and embeddings into an index directory."""
        target = Path(index_dir)
        target.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "id": r.id,
                "text": r.text,
                "metadata": r.metadata,
                "space_id": r.space_id,
            }
            for r in self._records
        ]
        (target / _RECORDS_FILENAME).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        if self._embeddings is not None:
            np.save(target / _EMBEDDINGS_FILENAME, self._embeddings)

    @classmethod
    def load(cls, index_dir: str | Path, *, space_id: str | None = None) -> VectorBackend:
        """Load a persisted backend from an index directory."""
        target = Path(index_dir)
        records_path = target / _RECORDS_FILENAME
        embeddings_path = target / _EMBEDDINGS_FILENAME
        if not records_path.is_file():
            raise FileNotFoundError(f"No persisted index at {target}")
        data = json.loads(records_path.read_text(encoding="utf-8"))
        records = [IndexRecord(**item) for item in data]
        embeddings = (
            np.load(embeddings_path) if embeddings_path.is_file() else None
        )
        return cls(records, embeddings, space_id=space_id)

    @classmethod
    def exists(cls, index_dir: str | Path) -> bool:
        """Return True if a persisted index exists at the directory."""
        return (Path(index_dir) / _RECORDS_FILENAME).is_file()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _infer_dimension(self) -> int:
        for record in self._records:
            vec = record.embedding
            if vec is not None:
                return int(np.asarray(vec).shape[0])
        return 0

    def embeddings(self) -> np.ndarray | None:
        """Return the (N, D) embedding matrix, or None."""
        return self._embeddings

    def records(self) -> list[IndexRecord]:
        """Return the indexed records."""
        return list(self._records)
