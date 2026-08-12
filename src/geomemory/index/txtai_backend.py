"""TxtaiBackend — txtai-based retrieval backend implementation.

txtai provides sparse (FTS-like) and dense (vector) retrieval with a unified
``Embeddings`` database. This backend satisfies the ``RetrievalBackend``
protocol and is used when the ``[ai]`` optional group is installed.

Importing this module lazily imports txtai so the core package works without
the heavy dependency installed.
"""

from __future__ import annotations

from typing import Any

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest


class TxtaiBackend:
    """Wrap a txtai ``Embeddings`` database.

    The txtai database is constructed on first use. ``upsert`` inserts
    ``IndexRecord`` entries with their precomputed embeddings (when present);
    otherwise txtai computes embeddings lazily via its configured path.
    """

    def __init__(self, index_dir: str, space_id: str = "text.nomic.v1") -> None:
        try:
            from txtai.embeddings import Embeddings  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on optional dep
            raise ImportError(
                "TxtaiBackend requires txtai. Install with `pip install geomemory[ai]`."
            ) from exc
        self._Embeddings = Embeddings
        self.index_dir = index_dir
        self.space_id = space_id
        self._db: Any = None

    @property
    def db(self) -> Any:
        """Lazily build and return the txtai database."""
        if self._db is None:
            self._db = self._Embeddings(path=self.index_dir, content=True, hybrid=True, sparse=True)
        return self._db

    # ── Protocol implementation ──────────────────────────────────────────────

    def upsert(self, records: list[IndexRecord]) -> None:
        """Insert or update records in the txtai database."""
        if not records:
            return
        rows: list[dict[str, Any]] = []
        for record in records:
            row: dict[str, Any] = {"id": record.id, "text": record.text}
            if record.embedding is not None:
                row["embedding"] = record.embedding
            row.update(record.metadata)
            rows.append(row)
        self.db.index(rows)

    def delete(self, ids: list[str]) -> None:
        """Delete records by id."""
        if not ids:
            return
        self.db.delete(ids)

    def count(self) -> int:
        """Return the number of indexed records."""
        return len(self.db) if self._db is not None else 0

    def rebuild(self, manifest: IndexManifest) -> None:
        """Rebuild the index from a manifest.

        A fresh database is created at the index directory; callers should
        re-embed and re-upsert after calling this.
        """
        self._db = self._Embeddings(manifest=manifest.to_json(), content=True, hybrid=True, sparse=True)

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Execute a hybrid search through txtai."""
        if request.mode == "sparse":
            results = self.db.search(request.query, limit=request.top_k)
        elif request.mode == "dense":
            results = self.db.search(request.query, limit=request.top_k)
        else:
            results = self.db.search(request.query, limit=request.top_k)
        hits: list[SearchHit] = []
        for item in results:
            text = str(item.get("text", ""))
            score = float(item.get("score", 0.0))
            metadata: dict[str, Any] = {k: v for k, v in item.items() if k not in ("id", "text", "score")}
            hits.append(
                SearchHit(
                    id=str(item.get("id", "")),
                    score=score,
                    dense_score=score,
                    text=text,
                    locator=metadata.get("locator", {}),
                    metadata=metadata,
                )
            )
        return hits