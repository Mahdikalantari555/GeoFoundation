"""GeoTIFF/COG reader using rasterio (optional dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from geomemory.core.exceptions import RasterBackendUnavailableError
from geomemory.rs.raster.metadata import (
    RasterSceneData,
    acquired_from_metadata,
    bbox_from_bounds,
    build_band_specs,
    footprint_wkb_hex,
    sensor_from_metadata,
    validate_bbox,
)


def _default_backend() -> Any:
    """Import rasterio lazily, raising a domain error when it is missing."""
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RasterBackendUnavailableError(
            "Raster operations require rasterio. Install with `pip install geomemory[rs]`."
        ) from exc
    return rasterio


class RasterReader:
    """Read GeoTIFF/COG metadata and pixel windows.

    The rasterio backend is injectable for testing; when ``backend`` is None the
    real ``rasterio`` module is imported lazily on first use.
    """

    def __init__(self, *, backend: Any | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> Any:
        """Return the rasterio-compatible backend, loading it on first use."""
        if self._backend is None:
            self._backend = _default_backend()
        return self._backend

    def read_scene(self, path: str | Path) -> RasterSceneData:
        """Extract scene metadata (CRS, bbox, bands, sensor, acquisition date)."""
        dataset = self.backend.open(str(path))
        try:
            crs = _crs_string(dataset.crs)
            bounds = tuple(dataset.bounds)  # (left, bottom, right, top) in file CRS
            wgs_bounds = _wgs84_bounds(crs, bounds)
            bbox = bbox_from_bounds(*wgs_bounds)
            validate_bbox(bbox)
            meta = dict(dataset.tags() or {})
            bands = build_band_specs(
                dataset.count, dtypes=list(dataset.dtypes), width=dataset.width, height=dataset.height
            )
            descriptions = list(getattr(dataset, "descriptions", None) or [])
            for i in range(dataset.count):
                if i < len(descriptions) and descriptions[i]:
                    bands[i]["description"] = descriptions[i]
            return RasterSceneData(
                crs=crs,
                bbox=bbox,
                transform=_transform_list(dataset.transform),
                bands=bands,
                sensor=sensor_from_metadata(meta),
                acquired_at=acquired_from_metadata(meta),
                dtype=dataset.dtypes[0] if dataset.dtypes else None,
                nodata=dataset.nodata,
                width=int(dataset.width),
                height=int(dataset.height),
                resolution_m=_resolution_m(dataset.transform, crs),
                footprint=footprint_wkb_hex(bbox),
                metadata=meta,
            )
        finally:
            dataset.close()

    def read_window(self, path: str | Path, window: dict[str, int]) -> np.ndarray:
        """Read a window [x, y, width, height] as a float32 (bands, height, width) array."""
        dataset = self.backend.open(str(path))
        try:
            return np.asarray(dataset.read(window=window), dtype=np.float32)
        finally:
            dataset.close()

    def read_all(self, path: str | Path) -> np.ndarray:
        """Read the full raster as a float32 (bands, height, width) array."""
        dataset = self.backend.open(str(path))
        try:
            return np.asarray(dataset.read(), dtype=np.float32)
        finally:
            dataset.close()


def _crs_string(crs: Any) -> str:
    """Normalize a rasterio CRS (or string) to an EPSG:xxxx string."""
    if crs is None:
        return "EPSG:4326"
    if isinstance(crs, str):
        return crs.upper() if crs.upper().startswith("EPSG:") else f"EPSG:{crs}"
    to_epsg = getattr(crs, "to_epsg", None)
    if to_epsg is not None:
        code = to_epsg()
        if code:
            return f"EPSG:{int(code)}"
    to_string = getattr(crs, "to_string", None)
    if to_string is not None:
        value = to_string()
        if value and "EPSG" in value.upper():
            return value.upper()
    return "EPSG:4326"


def _wgs84_bounds(crs: str, bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Reproject (left, bottom, right, top) bounds into EPSG:4326 when possible."""
    if crs == "EPSG:4326":
        return bounds
    try:
        from rasterio.warp import transform_bounds
    except ImportError:  # pragma: no cover - optional dependency
        return bounds
    return tuple(float(v) for v in transform_bounds(crs, "EPSG:4326", *bounds))


def _transform_list(transform: Any) -> list[float]:
    """Convert an affine transform (object or iterable) to a 6-value list."""
    if transform is None:
        return []
    if isinstance(transform, (list, tuple)):
        values = list(transform)
    else:
        try:
            values = [
                float(getattr(transform, name))
                for name in ("a", "b", "c", "d", "e", "f")
            ]
        except (AttributeError, TypeError, ValueError):  # pragma: no cover
            return []
    return [float(v) for v in values]


def _resolution_m(transform: Any, crs: str) -> float | None:
    """Approximate pixel resolution in meters."""
    values = _transform_list(transform)
    if not values:
        return None
    a = values[0]
    if crs == "EPSG:4326":
        return abs(a) * 111320.0
    return abs(a)
