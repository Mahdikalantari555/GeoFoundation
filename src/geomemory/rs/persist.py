"""Persistence helpers for raster scenes and vector layers."""

from __future__ import annotations

import sqlite3
from typing import Any

from geomemory.core.models import RasterScene, RasterTile, VectorLayer
from geomemory.storage.repositories.spatial_repo import (
    RasterSceneRepository,
    RasterTileRepository,
    SpatialRepository,
    VectorLayerRepository,
)


def spatial_metadata(
    *,
    bbox: list[float] | None = None,
    acquired_at: str | None = None,
    sensor: str | None = None,
) -> dict[str, Any]:
    """Build the segment ``metadata["spatial"]`` payload used by search filters."""
    return {key: value for key, value in {
        "bbox": bbox,
        "acquired_at": acquired_at,
        "sensor": sensor,
    }.items() if value is not None}


def persist_scene(
    conn: sqlite3.Connection,
    revision_id: str,
    scene_data: dict[str, Any],
    *,
    tiles: list[dict[str, Any]] | None = None,
) -> RasterScene:
    """Persist a raster scene (+ tiles) and its RTree spatial index entry."""
    scene = RasterScene(
        revision_id=revision_id,
        sensor=scene_data.get("sensor"),
        bands=list(scene_data.get("bands") or []),
        crs=scene_data.get("crs") or "EPSG:4326",
        footprint=scene_data.get("footprint"),
        bbox=list(scene_data.get("bbox") or []),
        acquired_at=scene_data.get("acquired_at"),
        transform=list(scene_data.get("transform") or []),
        dtype=scene_data.get("dtype"),
        nodata=scene_data.get("nodata"),
        width=scene_data.get("width"),
        height=scene_data.get("height"),
        resolution_m=scene_data.get("resolution_m"),
        metadata=dict(scene_data.get("metadata") or {}),
    )
    RasterSceneRepository(conn).insert(scene)
    if len(scene.bbox) == 4:
        SpatialRepository(conn).insert(scene.id, scene.bbox)

    for tile_data in tiles or []:
        tile = RasterTile(
            scene_id=scene.id,
            window=dict(tile_data.get("window") or {}),
            transform=list(tile_data.get("transform") or []),
            footprint=tile_data.get("footprint"),
            preview_path=tile_data.get("preview_path"),
            metadata=dict(tile_data.get("metadata") or {}),
        )
        RasterTileRepository(conn).insert(tile)
    return scene


def persist_vector_layer(
    conn: sqlite3.Connection,
    revision_id: str,
    layer_data: dict[str, Any],
) -> VectorLayer:
    """Persist a vector layer and its RTree spatial index entry."""
    layer = VectorLayer(
        revision_id=revision_id,
        geometry_type=layer_data.get("geometry_type") or "GeometryCollection",
        crs=layer_data.get("crs") or "EPSG:4326",
        footprint=layer_data.get("footprint"),
        feature_count=int(layer_data.get("feature_count") or 0),
        metadata={
            "bbox": list(layer_data.get("bbox") or []),
            "properties": list(layer_data.get("properties") or []),
            **dict(layer_data.get("metadata") or {}),
        },
    )
    VectorLayerRepository(conn).insert(layer)
    bbox = layer.metadata.get("bbox") or []
    if len(bbox) == 4:
        SpatialRepository(conn).insert(layer.id, bbox)
    return layer
