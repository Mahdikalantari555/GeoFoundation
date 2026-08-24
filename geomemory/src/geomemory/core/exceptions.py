"""Domain exception hierarchy for GeoMemory."""

from __future__ import annotations


class GeoMemoryError(Exception):
    """Base class for all GeoMemory domain errors."""


class WorkspaceNotFoundError(GeoMemoryError):
    """Raised when opening a path that is not an existing GeoMemory workspace."""


class WorkspaceExistsError(GeoMemoryError):
    """Raised when creating a workspace at a path that already exists."""


class DatabaseError(GeoMemoryError):
    """Raised when the SQLite database fails to open, migrate, or query."""


class CollectionNotFoundError(GeoMemoryError):
    """Raised when a collection_id does not exist or is archived."""


class AssetNotFoundError(GeoMemoryError):
    """Raised when an asset_id does not exist."""


class RevisionNotFoundError(GeoMemoryError):
    """Raised when an asset revision does not exist."""


class UnsupportedFormatError(GeoMemoryError):
    """Raised when no loader supports the given source."""


class ModelNotLoadedError(GeoMemoryError):
    """Raised when a model backend is required but not loaded.

    The ``hint`` attribute carries the configured model path (if any) so
    callers can surface a helpful message.
    """

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class NetworkDisabledError(GeoMemoryError):
    """Raised when a source requires network access but offline mode is on."""


class AbstentionError(GeoMemoryError):
    """Raised internally to signal the QA layer should abstain.

    This is caught by the chat service and converted into an abstaining
    :class:`~geomemory.core.models.Answer` — it should never escape to
    callers of ``ask()``.
    """


class SpatialValidationError(GeoMemoryError):
    """Raised for invalid spatial inputs (e.g. antimeridian crossing)."""


class RasterBackendUnavailableError(GeoMemoryError):
    """Raised when a raster operation requires rasterio but it is not installed."""


class VectorBackendUnavailableError(GeoMemoryError):
    """Raised when a vector operation requires geopandas but it is not installed."""


class BandMappingError(GeoMemoryError):
    """Raised when a spectral index is requested with a missing or invalid band mapping."""


class ValidationError(GeoMemoryError):
    """Raised when domain validation fails outside Pydantic's scope."""