"""Embedder selection factories (text + vision)."""

from __future__ import annotations

import importlib
import warnings
from typing import TYPE_CHECKING

from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder, VisionEmbedder

if TYPE_CHECKING:
    from geomemory.core.models import WorkspaceSettings
    from geomemory.embeddings.provider import EmbeddingProvider


def build_text_embedder(settings: WorkspaceSettings) -> EmbeddingProvider:
    """Return a text EmbeddingProvider based on workspace settings.

    Resolves ``embedding_provider`` (new) and the deprecated
    ``embedding_backend`` alias. ``sentence-transformers`` alias maps to
    ``onnx`` with a deprecation warning and triggers ``ReindexRequired`` via
    space_id mismatch elsewhere.
    """
    # Resolve provider: prefer new field, fall back to deprecated backend alias.
    provider = getattr(settings, "embedding_provider", None)
    # Legacy alias mapping
    backend = getattr(settings, "embedding_backend", "hashing")
    if provider is None or provider == "onnx" and backend == "sentence-transformers":
        # Detect legacy ST usage — warn once
        if backend == "sentence-transformers":
            warnings.warn(
                "embedding_backend='sentence-transformers' is deprecated; "
                "use embedding_provider='onnx' with onnx_model_name='Xenova/all-MiniLM-L6-v2'. "
                "Existing indexes with space_id text.st.* require reindex via `geomemory reindex`.",
                DeprecationWarning,
                stacklevel=2,
            )
            provider = "onnx"
        elif not provider:
            provider = backend if backend in ("onnx", "openai", "voyage", "custom", "hashing", "llama-cpp") else "onnx"
            # hashing / llamacpp are legacy text backends; map to hashing or onnx
            if provider == "hashing":
                from geomemory.embeddings.hashing_text import HashingTextEmbedder as _Hash

                # HashingTextEmbedder satisfies EmbeddingProvider shape via duck typing
                return _Hash()  # type: ignore[return-value]
            if provider == "llama-cpp":
                try:
                    from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder

                    mp = getattr(settings, "embedding_path", None) or getattr(settings, "model_path", None)
                    if mp:
                        return LlamaCppTextEmbedder(mp)  # type: ignore[return-value]
                except Exception:
                    pass
                from geomemory.embeddings.hashing_text import HashingTextEmbedder as _Hash2

                return _Hash2()  # type: ignore[return-value]

    # Canonical onnx path
    if provider in (None, "onnx"):
        from geomemory.embeddings.provider import ONNXEmbeddingProvider

        model_name = getattr(settings, "onnx_model_name", "Xenova/all-MiniLM-L6-v2")
        # Legacy ST name normalization is also handled inside the provider
        if not model_name or model_name == "sentence-transformers/all-MiniLM-L6-v2":
            # Keep hub default but prefer Xenova quantized
            model_name = "Xenova/all-MiniLM-L6-v2"
        return ONNXEmbeddingProvider(model_name, offline=getattr(settings, "offline", False))

    if provider == "openai":
        from geomemory.embeddings.provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(getattr(settings, "onnx_model_name", ""))

    if provider == "voyage":
        from geomemory.embeddings.provider import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider(getattr(settings, "onnx_model_name", ""))

    if provider == "custom":
        from geomemory.embeddings.provider import CustomEmbeddingProvider

        return CustomEmbeddingProvider(getattr(settings, "onnx_model_name", ""))

    if provider == "hashing":
        from geomemory.embeddings.hashing_text import HashingTextEmbedder as _Hash3

        return _Hash3()  # type: ignore[return-value]

    # Fallback — onnx
    from geomemory.embeddings.provider import ONNXEmbeddingProvider

    return ONNXEmbeddingProvider(getattr(settings, "onnx_model_name", "Xenova/all-MiniLM-L6-v2"))


def build_vision_embedder(settings: WorkspaceSettings) -> VisionEmbedder:
    """Return a vision embedder based on workspace settings.

    - If ``vision_path`` is set and ``torch`` is importable, returns an
       :class:`OlmoEarthVisionEmbedder`.
    - Otherwise, returns :class:`PlaceholderVisionEmbedder`.
    """
    vision_path = settings.vision_path
    if vision_path is None:
        return PlaceholderVisionEmbedder()

    try:
        importlib.import_module("torch")
    except ImportError:
        return PlaceholderVisionEmbedder()

    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

    return OlmoEarthVisionEmbedder(vision_path)
