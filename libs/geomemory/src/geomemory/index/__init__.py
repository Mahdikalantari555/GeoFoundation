"""Retrieval backends: protocol, txtai implementation, numpy fallback, image index."""

from __future__ import annotations

from geomemory.index.backend import RetrievalBackend
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import (
    create_manifest,
    load_manifest,
    manifest_exists,
    write_manifest,
)
from geomemory.index.numpy_backend import NumpyBackend
from geomemory.index.qdrant_backend import QdrantBackend
from geomemory.index.txtai_backend import TxtaiBackend

__all__ = [
    "ImageIndex",
    "NumpyBackend",
    "QdrantBackend",
    "RetrievalBackend",
    "TxtaiBackend",
    "create_manifest",
    "load_manifest",
    "manifest_exists",
    "write_manifest",
]
