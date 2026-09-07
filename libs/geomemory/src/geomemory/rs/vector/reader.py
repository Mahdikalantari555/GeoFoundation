"""Vector layer reader (GeoJSON/GeoPackage) via geopandas (optional dependency)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from geomemory.core.exceptions import VectorBackendUnavailableError
from geomemory.core.models import GeoMemoryModel
from geomemory.rs.raster.metadata import (
    bbox_from_bounds,
    footprint_wkb_hex,
    format_bbox,
    validate_bbox,
)

_VALID_GEOMETRIES = (
    "Point",
    "LineString",
    "Polygon",
    "MultiPoint",
    "MultiLineString",
    "MultiPolygon",
    "GeometryCollection",
)


class VectorLayerData(GeoMemoryModel):
    """Parsed vector layer metadata (pre-persistence payload)."""

    geometry_type: str = "GeometryCollection"
    crs: str = "EPSG:4326"
    bbox: list[float] = Field(default_factory=list)  # [min_lon, min_lat, max_lon, max_lat]
    footprint: str | None = None
    feature_count: int = 0
    properties: list[str] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _default_backend() -> Any:
    """Import geopandas lazily, raising a domain error when it is missing."""
    try:
        import geopandas
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise VectorBackendUnavailableError(
            "Vector operations require geopandas. Install with `pip install geomemory[rs]`."
        ) from exc
    return geopandas


class VectorReader:
    """Read vector layers via an injectable geopandas-compatible backend."""

    def __init__(self, *, backend: Any | None = None) -> None:
        self._backend = backend

    @property
    def backend(self) -> Any:
        """Return the geopandas-compatible backend, loading it on first use."""
        if self._backend is None:
            self._backend = _default_backend()
        return self._backend

    def read_layer(self, path: str | Path) -> VectorLayerData:
        """Extract layer metadata (geometry type, CRS, bbox, features)."""
        data = self.backend.read_file(str(path))
        geometry = getattr(data, "geometry", None)
        if geometry is None or len(data) == 0:
            return VectorLayerData(
                geometry_type="GeometryCollection",
                crs=_crs_string(getattr(data, "crs", None)),
                feature_count=int(len(data)),
                metadata={"driver": getattr(data, "driver", None) or "unknown"},
            )
        types = set(geometry.geom_type)
        geometry_type = _pick_geometry(types)
        crs = _crs_string(getattr(data, "crs", None))
        bounds = tuple(geometry.total_bounds)  # (minx, miny, maxx, maxy)
        bbox = bbox_from_bounds(*bounds)
        validate_bbox(bbox)
        properties = [col for col in (list(data.columns) if data.columns is not None else []) if col != "geometry"]
        return VectorLayerData(
            geometry_type=geometry_type,
            crs=crs,
            bbox=bbox,
            footprint=footprint_wkb_hex(bbox),
            feature_count=int(len(data)),
            properties=properties,
            sample=_sample_features(data, properties),
            metadata={"driver": getattr(data, "driver", None) or "unknown"},
        )


def _pick_geometry(types: set[str]) -> str:
    """Choose a canonical geometry type from the set present in a layer."""
    for candidate in _VALID_GEOMETRIES:
        if candidate in types:
            return candidate
    for candidate in sorted(types):
        if candidate in _VALID_GEOMETRIES:
            return candidate
    return "GeometryCollection"


def _crs_string(crs: Any) -> str:
    """Normalize a geopandas CRS (or string) to an EPSG:xxxx string."""
    if crs is None:
        return "EPSG:4326"
    if isinstance(crs, str):
        return crs.upper() if crs.upper().startswith("EPSG:") else f"EPSG:{crs}"
    to_epsg = getattr(crs, "to_epsg", None)
    if to_epsg is not None:
        code = to_epsg()
        if code:
            return f"EPSG:{int(code)}"
    return "EPSG:4326"


def _sample_features(data: Any, properties: list[str], limit: int = 5) -> list[dict[str, Any]]:
    """Return the first few feature property records (best-effort)."""
    try:
        head = data.head(limit)
        if not hasattr(head, "to_dict"):
            return []
        return [{key: record.get(key) for key in properties} for record in head.to_dict("records")]
    except (AttributeError, TypeError, ValueError):
        return []


def describe_layer(layer: VectorLayerData) -> str:
    """Build a searchable text description for a vector layer."""
    parts = [f"Vector layer with {layer.feature_count} feature(s)."]
    parts.append(f"Geometry type: {layer.geometry_type}.")
    parts.append(f"CRS: {layer.crs}.")
    if layer.bbox:
        parts.append(f"Extent (WGS84): {format_bbox(layer.bbox)}.")
    if layer.properties:
        parts.append("Attributes: " + ", ".join(layer.properties) + ".")
    if layer.sample:
        parts.append(
            "Sample records: " + " ".join(json.dumps(record) for record in layer.sample[:3]) + "."
        )
    return " ".join(parts)
