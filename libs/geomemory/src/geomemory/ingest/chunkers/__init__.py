"""Chunker registry and built-in chunkers."""

from __future__ import annotations

from geomemory.core.plugin_registry import ChunkerRegistry
from geomemory.ingest.chunkers.fixed_size import FixedSizeChunker
from geomemory.ingest.chunkers.header_then_token import HeaderThenTokenChunker

DEFAULT_CHUNKER = "header_then_token"


def default_registry() -> ChunkerRegistry:
    """Return a registry with the built-in chunkers registered."""
    registry = ChunkerRegistry()
    registry.register("header_then_token", HeaderThenTokenChunker())
    registry.register("fixed_size", FixedSizeChunker())
    return registry


__all__ = [
    "DEFAULT_CHUNKER",
    "ChunkerRegistry",
    "FixedSizeChunker",
    "HeaderThenTokenChunker",
    "default_registry",
]
