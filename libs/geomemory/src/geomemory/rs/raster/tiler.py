"""Tile generation for large rasters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geomemory.rs.raster.metadata import RasterSceneData, RasterTileData, footprint_wkb_hex
from geomemory.rs.raster.preview import compute_preview_array, write_png


def window_grid(width: int, height: int, tile_size: int = 256) -> list[dict[str, int]]:
    """Compute a grid of non-overlapping tile windows for a raster extent."""
    if width <= 0 or height <= 0:
        return []
    windows: list[dict[str, int]] = []
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            windows.append(
                {
                    "x": x,
                    "y": y,
                    "width": min(tile_size, width - x),
                    "height": min(tile_size, height - y),
                }
            )
    return windows


def window_transform(transform: list[float], window: dict[str, int]) -> list[float]:
    """Compute the affine transform for a window within a scene."""
    if len(transform) < 6:
        return []
    a, b, c, d, e, f = transform[:6]
    x, y = window["x"], window["y"]
    return [a, b, a * x + b * y + c, d, e, d * x + e * y + f]


def window_bounds(
    transform: list[float], window: dict[str, int]
) -> tuple[float, float, float, float]:
    """Return (left, bottom, right, top) bounds for a window in scene CRS."""
    if len(transform) < 6:
        return (0.0, 0.0, 0.0, 0.0)
    a, b, c, d, e, f = transform[:6]
    x, y = window["x"], window["y"]
    w, h = window["width"], window["height"]
    left = a * x + b * y + c
    top = d * x + e * y + f
    right = a * (x + w) + b * (y + h) + c
    bottom = d * (x + w) + e * (y + h) + f
    return (left, bottom, right, top)


def build_tiles(
    scene: RasterSceneData,
    source_path: str | Path,
    output_dir: str | Path,
    *,
    reader: Any | None = None,
    tile_size: int = 256,
    max_side: int = 256,
) -> list[RasterTileData]:
    """Generate tiles for a scene, writing best-effort PNG previews.

    When ``reader`` is provided, each window is read and downsampled to a
    preview image written under ``output_dir``; if Pillow is unavailable the
    preview is skipped (``preview_path`` stays None) but the window is kept.
    """
    tiles: list[RasterTileData] = []
    for window in window_grid(scene.width or 0, scene.height or 0, tile_size):
        transform = window_transform(scene.transform, window)
        footprint = None
        if scene.crs == "EPSG:4326":
            left, bottom, right, top = window_bounds(transform, window)
            footprint = footprint_wkb_hex([left, bottom, right, top])
        preview_path: str | None = None
        if reader is not None:
            try:
                array = reader.read_window(source_path, window)
                preview = compute_preview_array(array, max_side=max_side)
                relative = Path("tiles") / f"{scene.title or 'scene'}_{len(tiles)}.png"
                target = Path(output_dir) / relative
                if write_png(preview, target):
                    preview_path = str(target)
            except Exception:  # noqa: BLE001 - best-effort tile preview
                preview_path = None
        tiles.append(
            RasterTileData(
                window=window,
                transform=transform,
                footprint=footprint,
                preview_path=preview_path,
            )
        )
    return tiles


def window_only_tiles(
    scene: RasterSceneData, tile_size: int = 256
) -> list[RasterTileData]:
    """Build tile definitions (windows + transforms) without reading pixels."""
    tiles: list[RasterTileData] = []
    for window in window_grid(scene.width or 0, scene.height or 0, tile_size):
        transform = window_transform(scene.transform, window)
        footprint = None
        if scene.crs == "EPSG:4326":
            left, bottom, right, top = window_bounds(transform, window)
            footprint = footprint_wkb_hex([left, bottom, right, top])
        tiles.append(RasterTileData(window=window, transform=transform, footprint=footprint))
    return tiles

