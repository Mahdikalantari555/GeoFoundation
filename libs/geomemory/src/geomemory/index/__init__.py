"""Retrieval backends: protocol, txtai implementation, numpy fallback, image index."""

from __future__ import annotations

from geomemory.index.backend import RetrievalBackend
from geomemory.index.image_index import ImageIndex
from geomemory.index.lance_backend import LanceBackend
from geomemory.index.manifest import (
    create_manifest,
    load_manifest,
    manifest_exists,
    write_manifest,
)
from geomemory.index.numpy_backend import NumpyBackend
from geomemory.index.qdrant_backend import QdrantBackend
from geomemory.index.storage_backend import StorageBackend
from geomemory.index.txtai_backend import TxtaiBackend
from geomemory.index.vector_backend import VectorBackend

__all__ = [
    "ImageIndex",
    "LanceBackend",
    "NumpyBackend",
    "QdrantBackend",
    "RetrievalBackend",
    "StorageBackend",
    "TxtaiBackend",
    "VectorBackend",
    "create_manifest",
    "load_manifest",
    "manifest_exists",
    "write_manifest",
]