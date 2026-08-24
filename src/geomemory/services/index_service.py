"""IndexService — builds and maintains persisted retrieval indexes.

The service embeds workspace segments (via a configured GGUF embedder or the
offline :class:`HashingTextEmbedder`), persists ``EmbeddingRecord`` rows in
SQLite, and writes a :class:`VectorBackend` + ``IndexManifest`` under
``index_dir/<space_id>``. Dense search then loads the persisted backend
instead of rebuilding vectors on every call.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from geomemory.core.models import (
    EmbeddingRecord,
    IndexRecord,
    SearchHit,
    SearchRequest,
    WorkspaceSettings,
)
from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder
from geomemory.index.manifest import create_manifest, load_manifest, write_manifest
from geomemory.index.vector_backend import VectorBackend
from geomemory.storage.repositories.embedding_repo import EmbeddingRepository

if TYPE_CHECKING:
    from geomemory.embeddings.sentence_transformer import SentenceTransformerEmbedder
    from geomemory.index.qdrant_backend import QdrantBackend


class IndexService:
    """Build, rebuild, and query persisted dense indexes over segments."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        index_dir: str | Path,
        *,
        settings: WorkspaceSettings | None = None,
        batch_size: int = 64,
    ) -> None:
        self.conn = conn
        self.index_dir = Path(index_dir)
        self._settings = settings
        self.batch_size = batch_size

    # ── Build / rebuild ──────────────────────────────────────────────────────

    def build(
        self,
        space_id: str,
        *,
        model_path: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Embed all segments and persist a dense index for ``space_id``.

        Segments already embedded in the space are skipped unless ``force`` is
        set. Returns a summary dict with counts.
        """
        embedder = self._embedder(model_path)
        repo = EmbeddingRepository(self.conn)
        backend_dir = self.index_dir / space_id

        if force:
            repo.delete_by_space(space_id)
            if backend_dir.exists():
                shutil.rmtree(backend_dir)

        segments = self._load_segments()
        existing = {r.target_id for r in repo.get_by_space(space_id)}
        pending = [s for s in segments if s["id"] not in existing]

        records: list[IndexRecord] = []
        vectors: list[np.ndarray] = []
        for i in range(0, len(pending), self.batch_size):
            batch = pending[i : i + self.batch_size]
            texts = [s["text"] for s in batch]
            embedded = embedder.embed(texts)
            for j, seg in enumerate(batch):
                vec = embedded[j]
                record = EmbeddingRecord.from_vector(
                    target_id=seg["id"],
                    target_type="segment",
                    space_id=space_id,
                    model_id=embedder.model_id,
                    vector=vec,
                )
                repo.insert(record)
                records.append(
                    IndexRecord(
                        id=seg["id"],
                        text=seg["text"],
                        space_id=space_id,
                        metadata={
                            "locator": seg["locator"],
                            "revision_id": seg["revision_id"],
                            "segment_type": seg["segment_type"],
                            **seg["metadata"],
                        },
                    )
                )
                vectors.append(vec)

        if self._settings is not None and self._settings.vector_backend == "qdrant":
            # Server-mode Qdrant backend: vectors live server-side, no disk save.
            qdrant = self._qdrant_backend(space_id)
            if records:
                qdrant.upsert(records, embeddings=np.stack(vectors))
            qdrant.count()  # ensure reachable; raises on connection failure
        else:
            # Local on-disk backend (default).
            if VectorBackend.exists(backend_dir):
                backend: VectorBackend = VectorBackend.load(backend_dir, space_id=space_id)
                if records:
                    backend.upsert(records, embeddings=np.stack(vectors))
            else:
                backend = VectorBackend(space_id=space_id)
                if records:
                    backend.upsert(records, embeddings=np.stack(vectors))
            backend.save(backend_dir)

        manifest = create_manifest(
            space_id=space_id,
            model_id=embedder.model_id,
            dimension=embedder.embed(["x"]).shape[1],
            doc_count=backend.count(),
        )
        write_manifest(backend_dir, manifest)

        return {
            "space_id": space_id,
            "model_id": embedder.model_id,
            "embedded": len(pending),
            "total": len(segments),
            "indexed": backend.count(),
        }

    def rebuild(self, space_id: str, *, model_path: str | None = None) -> dict[str, Any]:
        """Rebuild the index for a space from scratch."""
        return self.build(space_id, model_path=model_path, force=True)

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        space_id: str,
        top_k: int = 20,
        model_path: str | None = None,
    ) -> list[SearchHit]:
        """Dense search over a persisted or server-side index.

        Returns an empty list when no index exists for the space.
        Routes to Qdrant when ``vector_backend`` is ``qdrant``; otherwise local.
        """
        settings = self._settings
        use_qdrant = (
            settings is not None
            and settings.vector_backend == "qdrant"
            and settings.qdrant_url
        )

        if use_qdrant:
            assert settings is not None
            backend = self._qdrant_backend(space_id)
            from geomemory.embeddings.sentence_transformer import (
                SentenceTransformerEmbedder,
            )

            st_embedder = SentenceTransformerEmbedder(settings.st_model_name)
            query_vec = st_embedder.embed_query([query])[0]
            request = SearchRequest(
                query=query,
                query_embedding=query_vec,
                mode="dense",
                top_k=top_k,
                top_n=top_k,
            )
            return backend.search(request)

        backend_dir = self.index_dir / space_id
        if not VectorBackend.exists(backend_dir):
            return []
        local_backend = VectorBackend.load(backend_dir, space_id=space_id)
        embedder = self._embedder(model_path)
        manifest = load_manifest(backend_dir)
        # Mismatch guard: warn if the query embedder differs from the one that built the index.
        if manifest.model_id != embedder.model_id:
            warnings.warn(
                f"embedding model mismatch: index built with '{manifest.model_id}' "
                f"but querying with '{embedder.model_id}'. Rebuild required for reliable results.",
                stacklevel=2,
            )
        query_vec = embedder.embed([query])[0]
        request = SearchRequest(
            query=query,
            query_embedding=query_vec,
            mode="dense",
            top_k=top_k,
            top_n=top_k,
        )
        return local_backend.search(request)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _embedder(
        self, model_path: str | None
    ) -> HashingTextEmbedder | LlamaCppTextEmbedder | SentenceTransformerEmbedder:
        """Return the configured embedder based on workspace settings.

        Dispatch order when ``self._settings`` is available:
          - ``sentence-transformers``: lazy-imported ST embedder.
          - ``llama-cpp`` / fallback when ``model_path`` is set: GGUF embedder.
          - ``hashing`` / fallback: offline hashing embedder.
        Falls back to the legacy (model_path ? llama-cpp : hashing) behavior when
        no settings were supplied.
        """
        settings = self._settings
        if settings is not None:
            if settings.embedding_backend == "sentence-transformers":
                return self._sentence_transformer_embedder(settings)
            if settings.embedding_backend == "llama-cpp":
                if model_path:
                    return LlamaCppTextEmbedder(model_path)
                return HashingTextEmbedder()
            # hashing: offline default
            return HashingTextEmbedder()
        # Legacy fallback.
        if model_path:
            return LlamaCppTextEmbedder(model_path)
        return HashingTextEmbedder()

    def _sentence_transformer_embedder(
        self, settings: WorkspaceSettings
    ) -> SentenceTransformerEmbedder:
        """Lazily import and construct the sentence-transformers embedder."""
        try:
            from geomemory.embeddings.sentence_transformer import (
                SentenceTransformerEmbedder,
            )
        except ImportError as exc:
            raise ImportError(
                "The sentence-transformers backend requires the optional "
                "`sentence-transformers` package. Install it with "
                "`pip install geomemory[st]`."
            ) from exc
        return SentenceTransformerEmbedder(settings.st_model_name)

    def _qdrant_backend(self, space_id: str) -> QdrantBackend:
        """Lazily import and construct the Qdrant backend for a space."""
        try:
            from geomemory.index.qdrant_backend import QdrantBackend
        except ImportError as exc:
            raise ImportError(
                "The qdrant vector backend requires the optional `qdrant-client` "
                "package. Install it with `pip install geomemory[vector]`."
            ) from exc
        settings = self._settings
        return QdrantBackend(
            space_id,
            url=settings.qdrant_url if settings else None,
            api_key=settings.qdrant_api_key if settings else None,
        )

    def _load_segments(self) -> list[dict[str, Any]]:
        """Load all segments from SQLite with parsed JSON fields."""
        rows = self.conn.execute(
            "SELECT s.id, s.text, s.locator, s.revision_id, s.segment_type, s.metadata "
            "FROM segment s ORDER BY s.created_at"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for r in rows:
            try:
                locator = json.loads(r["locator"]) if r["locator"] else {}
            except (json.JSONDecodeError, TypeError):
                locator = {}
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            result.append(
                {
                    "id": r["id"],
                    "text": r["text"],
                    "locator": locator,
                    "revision_id": r["revision_id"],
                    "segment_type": r["segment_type"],
                    "metadata": meta,
                }
            )
        return result
