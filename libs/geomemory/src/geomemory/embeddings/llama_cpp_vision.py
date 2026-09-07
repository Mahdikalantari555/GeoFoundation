"""OLMoEarth nano vision embedder via llama-cpp-python (experimental)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.embeddings.normalization import l2_normalize


class LlamaCppVisionEmbedder:
    """Embed image patches using an OLMoEarth nano GGUF checkpoint.

    Experimental: requires a user-provided GGUF checkpoint path and a
    llama-cpp-python build with vision support. The model is loaded lazily and
    raises :class:`ModelNotLoadedError` when the checkpoint path is unset.
    """

    space_id = "image.olmoearth.v1"

    def __init__(self, model_path: str, *, model_id: str = "olmoearth-nano") -> None:
        self.model_path = model_path
        self._model_id = model_id
        self._llm: Any = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> None:
        if self._llm is None:
            if not self.model_path:
                raise ModelNotLoadedError(
                    "Vision model path is not configured. Pass model_path or set "
                    "GEOMEMORY_MODEL_PATH in the workspace settings."
                )
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise ModelNotLoadedError(
                    "LlamaCppVisionEmbedder requires llama-cpp-python. "
                    "Install with `pip install geomemory[ai]`."
                ) from exc
            self._llm = Llama(model_path=self.model_path, embedding=True, verbose=False, n_ctx=4096)

    def embed_images(self, images: Sequence[Any]) -> np.ndarray:
        """Embed a sequence of image inputs (paths, bytes, or PIL images)."""
        self._load()
        assert self._llm is not None
        vectors: list[np.ndarray] = []
        for image in images:
            payload = _encode_image(image)
            out = self._llm.create_embedding(payload)
            vector = np.asarray(out["data"][0]["embedding"], dtype=np.float32)
            vectors.append(vector)
        return l2_normalize(np.stack(vectors, axis=0))

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray | None:
        """OLMoEarth nano is image-embedding only; returns None."""
        return None


def _encode_image(image: Any) -> Any:
    """Return a payload accepted by llama.cpp's vision embedding API."""
    if isinstance(image, (str, Path)):
        return str(image)
    if isinstance(image, (bytes, bytearray, memoryview)):
        return bytes(image)
    raise TypeError("image must be a path, bytes, or a PIL image object")
