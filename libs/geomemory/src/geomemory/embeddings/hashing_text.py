"""HashingTextEmbedder — deterministic offline text embedder.

This embedder produces a fixed-dimension, L2-normalized vector from character
n-gram hashing. It requires no model files, torch, or network access, so it is
the default embedder when no ``embedding_path`` is configured in workspace
settings. It satisfies the :class:`TextEmbedder` protocol.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

import numpy as np

from geomemory.embeddings.normalization import l2_normalize

_NGRAM = 3
_DIMENSION = 256
_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


class HashingTextEmbedder:
    """Hash-ngram TF embedder with a fixed, offline-safe vector space.

    ``space_id`` is ``text.hash.v1``. Vectors are deterministic for a given
    text and are L2-normalized so cosine similarity is equivalent to a dot
    product.
    """

    space_id = "text.hash.v1"

    def __init__(self, *, dimension: int = _DIMENSION, model_id: str = "hashing-ngram-v1") -> None:
        self._dimension = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a sequence of texts, returning an (N, D) float32 array."""
        vectors = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in self._tokenize(text):
                idx = self._hash_token(token) % self._dimension
                vectors[row, idx] += 1.0
        return l2_normalize(vectors)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed texts in batches of ``batch_size``."""
        results: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            results.append(self.embed(batch))
        return (
            np.concatenate(results, axis=0)
            if results
            else np.zeros((0, self._dimension), dtype=np.float32)
        )

    def _tokenize(self, text: str) -> list[str]:
        """Lowercase word tokens into character n-grams."""
        words = _TOKEN_RE.findall(text.lower())
        tokens: list[str] = []
        for word in words:
            if len(word) < _NGRAM:
                tokens.append(word)
                continue
            tokens.extend(word[i : i + _NGRAM] for i in range(len(word) - _NGRAM + 1))
        return tokens

    def _hash_token(self, token: str) -> int:
        """Return a stable 32-bit hash of a token."""
        digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
        return int.from_bytes(digest[:4], "little")
