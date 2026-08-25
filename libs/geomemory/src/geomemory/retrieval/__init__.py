"""Retrieval layer: query parsing, fusion, dedup, context packing, search service."""

from __future__ import annotations

from geomemory.retrieval.context_packer import estimate_tokens, format_context, pack_context
from geomemory.retrieval.deduplicator import deduplicate, enforce_diversity
from geomemory.retrieval.fusion import linear_fuse, rrf_fuse
from geomemory.retrieval.query_parser import QueryParser
from geomemory.retrieval.search_service import SearchService

__all__ = [
    "QueryParser",
    "SearchService",
    "deduplicate",
    "enforce_diversity",
    "estimate_tokens",
    "format_context",
    "linear_fuse",
    "pack_context",
    "rrf_fuse",
]