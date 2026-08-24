"""Image index manager for vision-embedded raster tiles.

Uses pure-numpy cosine similarity over stored tile embeddings, so it works
offline without txtai. Records and manifest are persisted under an index
directory for later queries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from geomemory.core.models import IndexManifest
from geomemory.embeddings.normalization import l2_normalize
from geomemory.index.manifest import write_manifest

_EMBEDDINGS_FILE = "embeddings.npy"
_IDS_FILE = "ids.json"


class ImageIndex:
    """In-memory index over image embeddings with numpy cosine search."""

    space_id = "image.olmoearth.v1"

    def __init__(self, *, embeddings: dict[str, np.ndarray] | None = None) -> None:
        self._embeddings: dict[str, np.ndarray] = dict(embeddings or {})

    def upsert(self, target_id: str, vector: np.ndarray) -> None:
        """Insert or replace an embedding for a target (tile/scene) id."""
        normalized = l2_normalize(np.asarray(vector, dtype=np.float32).reshape(1, -1))[0]
        self._embeddings[target_id] = normalized

    def delete(self, target_id: str) -> None:
        """Remove an embedding by target id."""
        self._embeddings.pop(target_id, None)

    def search(self, query_vector: np.ndarray, *, top_k: int = 10) -> list[dict[str, Any]]:
        """Return the top-k targets by cosine similarity to the query vector."""
        if not self._embeddings:
            return []
        ids = list(self._embeddings.keys())
        matrix = np.stack([self._embeddings[i] for i in ids])
        query = l2_normalize(np.asarray(query_vector, dtype=np.float32).reshape(1, -1))[0]
        scores = matrix @ query
        order = np.argsort(-scores)[:top_k]
        return [
            {"target_id": ids[int(i)], "score": float(scores[int(i)])} for i in order
        ]

    def count(self) -> int:
        """Return the number of indexed targets."""
        return len(self._embeddings)

    def ids(self) -> list[str]:
        """Return the indexed target ids."""
        return list(self._embeddings.keys())

    def save(self, index_dir: str | Path, manifest: IndexManifest) -> Path:
        """Persist embeddings, ids, and a manifest into an index directory."""
        target = Path(index_dir)
        target.mkdir(parents=True, exist_ok=True)
        ids = list(self._embeddings.keys())
        if ids:
            matrix = np.stack([self._embeddings[i] for i in ids])
        else:
            matrix = np.zeros((0, 0), dtype=np.float32)
        np.save(target / _EMBEDDINGS_FILE, matrix)
        (target / _IDS_FILE).write_text(json.dumps(ids), encoding="utf-8")
        return write_manifest(target, manifest)

    @classmethod
    def load(cls, index_dir: str | Path) -> ImageIndex:
        """Load an ImageIndex previously saved with :meth:`save`."""
        target = Path(index_dir)
        ids: list[str] = json.loads((target / _IDS_FILE).read_text(encoding="utf-8"))
        matrix = np.load(target / _EMBEDDINGS_FILE)
        if ids and matrix.ndim == 2 and matrix.shape[0] == len(ids):
            embeddings = {target_id: matrix[i] for i, target_id in enumerate(ids)}
        else:
            embeddings = {}
        return cls(embeddings=embeddings)
