"""Nomic GGUF text embedder via llama-cpp-python."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from geomemory.embeddings.normalization import l2_normalize


class LlamaCppTextEmbedder:
    """Embed text using a Nomic GGUF model loaded via llama-cpp-python.

    The model is loaded lazily on first use. ``space_id`` is ``text.nomic.v1``.
    """

    space_id = "text.nomic.v1"

    def __init__(self, model_path: str, *, model_id: str = "nomic-embed-text-v2-moe") -> None:
        self.model_path = model_path
        self._model_id = model_id
        self._llm = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> None:
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - optional dep
                raise ImportError(
                    "LlamaCppTextEmbedder requires llama-cpp-python. "
                    "Install with `pip install geomemory[ai]`."
                ) from exc
            self._llm = Llama(
                model_path=self.model_path,
                embedding=True,
                n_ctx=2048,
                verbose=False,
            )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a sequence of texts, returning an (N, D) float32 array."""
        self._load()
        assert self._llm is not None
        vectors: list[np.ndarray] = []
        for text in texts:
            out = self._llm.create_embedding(text)
            vec = np.asarray(out["data"][0]["embedding"], dtype=np.float32)
            vectors.append(vec)
        return l2_normalize(np.stack(vectors, axis=0))

    def embed_batch(self, texts: Sequence[str], batch_size: int) -> np.ndarray:
        """Embed texts in batches of ``batch_size``."""
        results: list[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            results.append(self.embed(batch))
        return np.concatenate(results, axis=0) if results else np.zeros((0, 0), dtype=np.float32)
