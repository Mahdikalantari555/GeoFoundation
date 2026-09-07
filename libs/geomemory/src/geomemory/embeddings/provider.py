"""EmbeddingProvider — provider abstraction for dense text embeddings.

Consumers (GeoMemory, SearchService, IndexService, RetrievalBackends) depend
only on this Protocol. The canonical implementation is ONNXEmbeddingProvider
(Xenova/all-MiniLM-L6-v2, quantized ONNX, 384-d, mean-pool + L2). Future
providers (OpenAI, Voyage, Custom) satisfy the same shape over HTTP.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class EmbeddingProvider(Protocol):
    """Provider abstraction for dense text embeddings."""

    @property
    def space_id(self) -> str:
        """Isolated embedding space identifier (e.g. text.onnx.Xenova-...v1)."""
        ...

    @property
    def model_id(self) -> str:
        """Underlying model identifier sent to the inference engine."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimension (e.g. 384 for MiniLM)."""
        ...

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed passages, returning (N, D) float32 L2-normalized."""
        ...

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        """Embed queries (may apply e5-style prefixes)."""
        ...

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed in batches of batch_size."""
        ...


# ---------------------------------------------------------------------------
# ONNX canonical provider
# ---------------------------------------------------------------------------


class ONNXEmbeddingProvider:
    """Canonical provider via onnxruntime + tokenizers + quantized ONNX.

    Wraps :class:`OnnxTextEmbedder` so callers depend only on the provider
    shape. Uses ``Xenova/all-MiniLM-L6-v2`` quantized weights by default
    (``onnx/model_quantized.onnx``, 384-d, mean-pool, L2).
    """

    def __init__(
        self,
        model_name: str = "Xenova/all-MiniLM-L6-v2",
        *,
        model_id: str | None = None,
        model_dir: str | Path | None = None,
        offline: bool = False,
    ) -> None:
        from geomemory.embeddings.onnx_text import OnnxTextEmbedder

        # Normalize legacy HF id "sentence-transformers/all-MiniLM-L6-v2" to
        # the quantized Xenova ONNX export when the caller did not explicitly
        # override to an onnx-community model.
        normalized = model_name
        if model_name == "sentence-transformers/all-MiniLM-L6-v2":
            normalized = "Xenova/all-MiniLM-L6-v2"
        self._inner = OnnxTextEmbedder(
            normalized, model_id=model_id, model_dir=model_dir, offline=offline
        )
        self._dimension = 384

    @property
    def space_id(self) -> str:
        return self._inner.space_id

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._inner.embed(texts), dtype=np.float32)

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(self._inner.embed_query(texts), dtype=np.float32)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        return np.asarray(self._inner.embed_batch(texts, batch_size), dtype=np.float32)

    # Hub parity hook
    def download_with_progress(self, on_progress: Any | None = None) -> str:
        return self._inner.download_with_progress(on_progress=on_progress)


# ---------------------------------------------------------------------------
# Future provider stubs (interface only, no network in this change)
# ---------------------------------------------------------------------------


class _StubProvider:
    """Base for not-yet-implemented cloud providers."""

    def __init__(self, model_name: str = "", **_kw: Any) -> None:
        self._model_name = model_name

    @property
    def space_id(self) -> str:
        safe = self._model_name.replace("/", "-").replace(".", "-") or "unknown"
        return f"text.{self.__class__.__name__.lower()}.{safe}.v1"

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return 0

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError(
            f"{self.__class__.__name__} not configured — set the API key env (e.g. OPENAI_API_KEY) "
            f"and implement HTTP retrieval, or use ONNXEmbeddingProvider for local inference."
        )

    def embed_query(self, texts: Sequence[str]) -> np.ndarray:
        return self.embed(texts)

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        return self.embed(texts)


class OpenAIEmbeddingProvider(_StubProvider):
    """Future OpenAI provider (stub — interface only)."""


class VoyageEmbeddingProvider(_StubProvider):
    """Future Voyage provider (stub — interface only)."""


class CustomEmbeddingProvider(_StubProvider):
    """Future custom provider (stub — interface only)."""
