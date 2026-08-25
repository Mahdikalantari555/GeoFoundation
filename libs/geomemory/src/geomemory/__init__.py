"""GeoMemory — multimodal, spatiotemporal knowledge engine for remote sensing research."""

from __future__ import annotations

__version__ = "0.1.0"

from geomemory.core.exceptions import (
    AbstentionError,
    AssetNotFoundError,
    CollectionNotFoundError,
    DatabaseError,
    GeoMemoryError,
    ModelNotLoadedError,
    NetworkDisabledError,
    UnsupportedFormatError,
    WorkspaceNotFoundError,
)
from geomemory.core.models import (
    Answer,
    Asset,
    AssetRevision,
    Citation,
    Collection,
    EmbeddingRecord,
    Job,
    QAResult,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchResult,
    Segment,
    SpatialFilter,
    TemporalFilter,
    Workspace,
)
from geomemory.core.workspace import GeoMemory

__all__ = [
    "__version__",
    # Entry point
    "GeoMemory",
    # Exceptions
    "AbstentionError",
    "AssetNotFoundError",
    "CollectionNotFoundError",
    "DatabaseError",
    "GeoMemoryError",
    "ModelNotLoadedError",
    "NetworkDisabledError",
    "UnsupportedFormatError",
    "WorkspaceNotFoundError",
    # Models
    "Answer",
    "Asset",
    "AssetRevision",
    "Citation",
    "Collection",
    "EmbeddingRecord",
    "Job",
    "QAResult",
    "RetrievalRun",
    "SearchFilters",
    "SearchResult",
    "SearchHit",
    "Segment",
    "SpatialFilter",
    "TemporalFilter",
    "Workspace",
]
