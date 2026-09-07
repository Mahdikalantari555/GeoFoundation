"""StorageBackend protocol — unified interface for all vector backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from geomemory.core.models import IndexRecord, SearchHit, SearchRequest


@runtime_checkable
class StorageBackend(Protocol):
    """Unified storage interface for vector backends.

    All backends (VectorBackend, LanceBackend, QdrantBackend) implement this
    protocol so IndexService can dispatch without type branches.
    """

    space_id: str

    def upsert(
        self, records: list[IndexRecord], embeddings: np.ndarray | None = None
    ) -> None:
        """Insert or replace records with their embedding vectors."""
        ...

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Execute a search and return ranked hits."""
        ...

    def count(self) -> int:
        """Return number of indexed records."""
        ...

    def save(self, path: str | Path) -> None:
        """Persist the index to a directory."""
        ...

    @classmethod
    def load(cls, path: str | Path, space_id: str | None = None) -> StorageBackend:  # type: ignore[misc]
        """Load a persisted index from a directory."""
        ...

    @classmethod
    def exists(cls, path: str | Path) -> bool:
        """Return True if a persisted index exists at the path."""
        ...
