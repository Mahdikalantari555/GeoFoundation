"""Embedding adapters: text and vision embedder protocols + llama.cpp adapters."""

from __future__ import annotations

from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.embeddings.hub import EmbeddingModelHub
from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder
from geomemory.embeddings.llama_cpp_vision import LlamaCppVisionEmbedder
from geomemory.embeddings.normalization import cosine_similarity, l2_normalize
from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
from geomemory.embeddings.onnx_text import OnnxTextEmbedder
from geomemory.embeddings.sentence_transformer import SentenceTransformerEmbedder
from geomemory.embeddings.text_embedder import TextEmbedder
from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder, VisionEmbedder

__all__ = [
    "EmbeddingModelHub",
    "HashingTextEmbedder",
    "LlamaCppTextEmbedder",
    "LlamaCppVisionEmbedder",
    "OlmoEarthVisionEmbedder",
    "OnnxTextEmbedder",
    "PlaceholderVisionEmbedder",
    "SentenceTransformerEmbedder",
    "TextEmbedder",
    "VisionEmbedder",
    "cosine_similarity",
    "l2_normalize",
]
