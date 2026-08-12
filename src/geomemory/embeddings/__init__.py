"""Embedding adapters: text and vision embedder protocols + llama.cpp adapters."""

from __future__ import annotations

from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder
from geomemory.embeddings.llama_cpp_vision import LlamaCppVisionEmbedder
from geomemory.embeddings.normalization import cosine_similarity, l2_normalize
from geomemory.embeddings.text_embedder import TextEmbedder
from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder, VisionEmbedder

__all__ = [
    "HashingTextEmbedder",
    "LlamaCppTextEmbedder",
    "LlamaCppVisionEmbedder",
    "PlaceholderVisionEmbedder",
    "TextEmbedder",
    "VisionEmbedder",
    "cosine_similarity",
    "l2_normalize",
]
