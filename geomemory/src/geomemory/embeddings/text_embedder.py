"""TextEmbedder protocol."""

from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np


class TextEmbedder(Protocol):
    """Protocol for text embedding models.

    Implementations produce vectors in a single, isolated embedding space
    identified by ``space_id``. Vectors from different spaces must never be
    compared directly.
    """

    @property
    def space_id(self) -> str:
        """Identifier of the embedding space (e.g. ``text.nomic.v1``)."""
        ...

    @property
    def model_id(self) -> str:
        """Identifier of the underlying model."""
        ...

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a sequence of texts, returning an (N, D) float32 array."""
        ...

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed texts in batches of ``batch_size``."""
        ...