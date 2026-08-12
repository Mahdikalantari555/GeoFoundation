"""Raster metadata payload models and pure helper functions."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from geomemory.core.exceptions import SpatialValidationError
from geomemory.core.models import GeoMemoryModel


class RasterSceneData(GeoMemoryModel):
    """Parsed raster scene metadata (pre-persistence payload)."""

    crs: str = "EPSG:4326"
    bbox: list[float] = Field(default_factory=list)  # [min_lon, min_lat, max_lon, max_lat]
    transform: list[float] = Field(default_factory=list)
    bands: list[dict[str, Any]] = Field(default_factory=list)
    sensor: str | None = None
    acquired_at: str | None = None
    dtype: str | None = None
    nodata: float | None = None
    width: int | None = None
    height: int | None = None
    resolution_m: float | None = None
    footprint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RasterTileData(GeoMemoryModel):
    """Windowed tile definition with optional preview path."""

    window: dict[str, int] = Field(default_factory=dict)  # x, y, width, height
    transform: list[float] = Field(default_factory=list)
    footprint: str | None = None
    preview_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def bbox_from_bounds(
    left: float, bottom: float, right: float, top: float
) -> list[float]:
    """Convert (left, bottom, right, top) bounds to [min_lon, min_lat, max_lon, max_lat]."""
    return [float(left), float(bottom), float(right), float(top)]


def validate_bbox(bbox: list[float]) -> None:
    """Validate a [min_lon, min_lat, max_lon, max_lat] bbox."""
    if len(bbox) != 4:
        raise SpatialValidationError(
            f"bbox must have exactly 4 values, got {len(bbox)}"
        )
    min_lon, min_lat, max_lon, max_lat = bbox
    if min_lon > max_lon or min_lat > max_lat:
        raise SpatialValidationError(
            f"Invalid bbox — min values exceed max values: {bbox}"
        )
    if min_lon < -180 or max_lon > 180 or min_lat < -90 or max_lat > 90:
        raise SpatialValidationError(
            f"Coordinate out of range — values must lie within WGS84 bounds: {bbox}"
        )


def format_bbox(bbox: list[float]) -> str:
    """Format a bbox for human-readable descriptions."""
    return "[" + ", ".join(f"{v:.6f}" for v in bbox) + "]"


def build_band_specs(
    count: int,
    *,
    dtypes: list[str] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> list[dict[str, Any]]:
    """Build a band list with index, dtype, and pixel dimensions."""
    dtypes = dtypes or []
    return [
        {
            "index": i + 1,
            "dtype": dtypes[i] if i < len(dtypes) else None,
            "width": width,
            "height": height,
        }
        for i in range(count)
    ]


def sensor_from_metadata(meta: dict[str, Any]) -> str | None:
    """Heuristically extract a sensor name from common raster metadata keys."""
    for key in ("SATELLITE", "PLATFORM", "SENSOR_NAME", "SENSOR", "MISSION"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


def acquired_from_metadata(meta: dict[str, Any]) -> str | None:
    """Heuristically extract an acquisition timestamp from common metadata keys."""
    for key in ("ACQUISITION_DATE", "DATE_ACQUIRED", "DATE", "DATETIME", "INGESTION_DATE"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


def footprint_wkb_hex(bbox: list[float]) -> str | None:
    """Return a WKB hex polygon for the bbox, or None if shapely is unavailable."""
    if len(bbox) != 4:
        return None
    try:
        from shapely import wkb
        from shapely.geometry import box
    except ImportError:  # pragma: no cover - optional dependency
        return None
    min_lon, min_lat, max_lon, max_lat = bbox
    return wkb.dumps(box(min_lon, min_lat, max_lon, max_lat), hex=True)


def describe_scene(scene: RasterSceneData) -> str:
    """Build a searchable text description for a raster scene."""
    parts = [f"Raster scene with {len(scene.bands)} band(s)."]
    if scene.sensor:
        parts.append(f"Sensor: {scene.sensor}.")
    if scene.acquired_at:
        parts.append(f"Acquired: {scene.acquired_at}.")
    parts.append(f"CRS: {scene.crs}.")
    if scene.bbox:
        parts.append(f"Extent (WGS84): {format_bbox(scene.bbox)}.")
    if scene.resolution_m:
        parts.append(f"Resolution: {scene.resolution_m:g} meters.")
    if scene.width and scene.height:
        parts.append(f"Size: {scene.width} x {scene.height} pixels.")
    band_names: list[str] = []
    for band in scene.bands:
        name = band.get("name") or f"Band {band.get('index', '?')}"
        description = band.get("description")
        band_names.append(f"{name} ({description})" if description else name)
    if band_names:
        parts.append("Bands: " + ", ".join(band_names) + ".")
    return " ".join(parts)
