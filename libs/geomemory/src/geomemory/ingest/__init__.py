"""Ingestion layer: loaders, chunkers, pipeline, and job queue."""

from __future__ import annotations

from geomemory.ingest.chunkers import (
    DEFAULT_CHUNKER,
    FixedSizeChunker,
    HeaderThenTokenChunker,
)
from geomemory.ingest.chunkers import (
    default_registry as default_chunker_registry,
)
from geomemory.ingest.loaders import (
    CodeLoader,
    DocxLoader,
    NotebookLoader,
    PdfLoader,
    TextLoader,
    get_loader,
)
from geomemory.ingest.loaders import (
    default_registry as default_loader_registry,
)

__all__ = [
    "CodeLoader",
    "DEFAULT_CHUNKER",
    "DocxLoader",
    "FixedSizeChunker",
    "HeaderThenTokenChunker",
    "NotebookLoader",
    "PdfLoader",
    "TextLoader",
    "default_chunker_registry",
    "default_loader_registry",
    "get_loader",
]
