"""QdrantBackend — server-mode Qdrant retrieval backend behind RetrievalBackend."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest


def _to_uuid5(space_id: str, record_id: str) -> str:
    """Deterministic UUID-5 for a record id within a space namespace."""
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"geomemory://space/{space_id}")
    return str(uuid.uuid5(namespace, record_id))


class QdrantBackend:
    """Dense retrieval backed by a Qdrant server, one collection per space."""

    def __init__(
        self,
        space_id: str,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection: str | None = None,
    ) -> None:
        self.space_id = space_id
        self._collection = collection or space_id
        self._url = url or "http://localhost:6333"
        self._api_key = api_key
        self._client = None
        self._dimension: int | None = None

    def _client_or_raise(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import QdrantClient  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ImportError(
                    "The qdrant vector backend requires the optional `qdrant-client` "
                    "package. Install it with `pip install geomemory[vector]`."
                ) from exc
            self._client = QdrantClient(url=self._url, api_key=self._api_key)
        return self._client

    def _ensure_collection(self, dimension: int) -> None:
        from qdrant_client.http import models as rest  # type: ignore[import-not-found]

        client = self._client_or_raise()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection not in existing:
            client.create_collection(
                collection_name=self._collection,
                vectors_config=rest.VectorParams(
                    size=dimension,
                    distance=rest.Distance.COSINE,
                ),
            )
        self._dimension = dimension

    def upsert(self, records: list[IndexRecord], *, embeddings: np.ndarray | None = None) -> None:
        if not records or embeddings is None:
            return
        from qdrant_client.http import models as rest

        self._ensure_collection(int(embeddings.shape[1]))
        points = [
            rest.PointStruct(
                id=_to_uuid5(self.space_id, r.id),
                vector=embeddings[i].tolist(),
                payload={
                    "id": r.id,
                    "text": r.text,
                    "metadata": r.metadata,
                    "space_id": r.space_id,
                },
            )
            for i, r in enumerate(records)
        ]
        self._client_or_raise().upsert(collection_name=self._collection, points=points)

    def search(self, request: SearchRequest) -> list[SearchHit]:
        if request.query_embedding is None:
            return []
        client = self._client_or_raise()
        q = np.asarray(request.query_embedding, dtype=np.float32).tolist()
        try:
            scored = client.search(
                collection_name=self._collection,
                query_vector=q,
                limit=request.top_k,
                with_payload=True,
            )
        except Exception as exc:
            raise ConnectionError(
                f"Qdrant search failed for collection '{self._collection}' at {self._url}: {exc}"
            ) from exc
        hits: list[SearchHit] = []
        for point in scored:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    id=payload.get("id", str(point.id)),
                    score=float(point.score),
                    dense_score=float(point.score),
                    text=payload.get("text", ""),
                    locator=(payload.get("metadata") or {}).get("locator", {}),
                    metadata=payload.get("metadata") or {},
                )
            )
        return hits

    def delete(self, ids: list[str]) -> None:
        from qdrant_client.http import models as rest

        client = self._client_or_raise()
        client.delete(
            collection_name=self._collection,
            points_selector=rest.PointIdsList(
                points=[_to_uuid5(self.space_id, i) for i in ids]
            ),
        )

    def rebuild(self, manifest: IndexManifest) -> None:
        """Rebuild is handled by the IndexService; not supported here."""
        raise NotImplementedError("Use IndexService.build to rebuild a QdrantBackend")

    def count(self) -> int:
        client = self._client_or_raise()
        try:
            info = client.get_collection(self._collection)
        except Exception as exc:
            raise ConnectionError(
                f"Qdrant connection failed for collection "
                f"'{self._collection}' at {self._url}: {exc}"
            ) from exc
        return int(info.points_count)

    # Compatibility no-ops so IndexService can treat backends uniformly.
    def save(self, index_dir: Any) -> None:  # noqa: ARG002
        """No-op: persistence is server-side."""

    @classmethod
    def load(cls, index_dir: Any, *, space_id: str | None = None) -> QdrantBackend:  # noqa: ARG002
        """Compatibility loader; returns a backend bound to the space."""
        return cls(space_id or "text.hash.v1")

    @classmethod
    def exists(cls, index_dir: Any) -> bool:  # noqa: ARG002
        """Compatibility check; always True for server-mode."""
        return True
