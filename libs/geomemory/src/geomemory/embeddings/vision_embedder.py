"""VisionEmbedder protocol and placeholder implementation."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

import numpy as np

from geomemory.core.exceptions import ModelNotLoadedError


class VisionEmbedder(Protocol):
    """Protocol for image embedding models.

    Images are accepted as paths, raw bytes, or PIL images. Implementations
    produce vectors in an isolated space identified by ``space_id``.
    """

    @property
    def space_id(self) -> str:
        """Identifier of the embedding space (e.g. ``image.olmoearth.v1``)."""
        ...

    @property
    def model_id(self) -> str:
        """Identifier of the underlying model."""
        ...

    def embed_images(self, images: Sequence[Any]) -> np.ndarray:
        """Embed a sequence of images, returning an (N, D) float32 array."""
        ...

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray | None:
        """Embed texts for text-to-image search, or None when unsupported."""
        ...


class PlaceholderVisionEmbedder:
    """Vision embedder stub that raises until a real model is configured."""

    space_id = "image.olmoearth.v1"
    model_id = "olmoearth-nano"

    def embed_images(self, images: Sequence[Any]) -> np.ndarray:
        """Raise ModelNotLoadedError (deferred pending a real model checkpoint)."""
        raise ModelNotLoadedError(
            "No vision embedder configured. Provide an OLMoEarth nano GGUF path "
            "and use LlamaCppVisionEmbedder."
        )

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray | None:
        """OLMoEarth nano does not support text embedding."""
        return None
