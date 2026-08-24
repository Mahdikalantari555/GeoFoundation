"""SentenceTransformerEmbedder — dense text embeddings via sentence-transformers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from geomemory.embeddings.normalization import l2_normalize

_E5_PREFIXES = {"query: ", "passage: "}


def _model_family(model_name: str) -> str:
    """Return a coarse family key from the model name."""
    lower = model_name.lower()
    if "e5" in lower:
        return "e5"
    if "bge" in lower:
        return "bge"
    return "generic"


class SentenceTransformerEmbedder:
    """Embed text using a sentence-transformers model, behind TextEmbedder.

    Lazy-imports ``sentence-transformers`` so the core package stays torch-free.
    Applies e5-family input prefixes (``query: `` / ``passage: ``) and reports
    a stable ``space_id`` derived from the model name.
    """

    def __init__(self, model_name: str, *, model_id: str | None = None) -> None:
        self.model_name = model_name
        self._model_id = model_id or model_name
        self._model: Any = None
        self._family = _model_family(model_name)

    @property
    def space_id(self) -> str:
        safe = self.model_name.replace("/", "-").replace(".", "-")
        return f"text.st.{safe}.v1"

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> Any:  # pragma: no cover - exercised via stub in tests
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "The sentence-transformers backend requires the optional "
                    "`sentence-transformers` package. Install it with "
                    "`pip install geomemory[st]`."
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _apply_prefix(self, texts: Sequence[str], *, query: bool) -> list[str]:
        if self._family != "e5":
            return list(texts)
        prefix = "query: " if query else "passage: "
        return [prefix + t for t in texts]

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a sequence of texts (passage path), L2-normalized."""
        model = self._load()
        prefixed = self._apply_prefix(texts, query=False)
        vectors = model.encode(prefixed, normalize_embeddings=False)
        return l2_normalize(np.asarray(vectors, dtype=np.float32))

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a sequence of texts (query path), L2-normalized."""
        model = self._load()
        prefixed = self._apply_prefix(texts, query=True)
        vectors = model.encode(prefixed, normalize_embeddings=False)
        return l2_normalize(np.asarray(vectors, dtype=np.float32))

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed texts in batches of ``batch_size``."""
        results: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            results.append(self.embed(batch))
        return (
            np.concatenate(results, axis=0)
            if results
            else np.zeros((0, 0), dtype=np.float32)
        )
