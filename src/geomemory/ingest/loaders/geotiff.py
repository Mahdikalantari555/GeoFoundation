"""GeoTIFF loader — produces a searchable scene description plus tile definitions."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.rs.raster.metadata import describe_scene
from geomemory.rs.raster.reader import RasterReader
from geomemory.rs.raster.tiler import build_tiles, window_only_tiles


class GeoTiffLoader:
    """Load GeoTIFF/COG files into a searchable raster scene payload.

    The reader is injectable for testing. When ``artifact_dir`` is set, tile
    preview PNGs are written there (best-effort; requires Pillow).
    """

    def __init__(
        self,
        *,
        reader: RasterReader | None = None,
        artifact_dir: str | Path | None = None,
        tile_size: int = 256,
        max_side: int = 256,
    ) -> None:
        self.reader = reader or RasterReader()
        self.artifact_dir = Path(artifact_dir) if artifact_dir else None
        self.tile_size = tile_size
        self.max_side = max_side

    def supports(self, source: SourceRef) -> bool:
        """Return True for GeoTIFF files (by extension)."""
        if source.path is None:
            return False
        return Path(source.path).suffix.lower() in (".tif", ".tiff")

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        """Read scene metadata and yield a single ParsedObject."""
        if source.path is None:
            raise ValueError("GeoTiffLoader requires a local file path")
        scene = self.reader.read_scene(source.path)
        if self.artifact_dir is not None:
            tiles = build_tiles(
                scene,
                source.path,
                self.artifact_dir,
                reader=self.reader,
                tile_size=self.tile_size,
                max_side=self.max_side,
            )
        else:
            tiles = window_only_tiles(scene, tile_size=self.tile_size)

        title = Path(source.path).name
        yield ParsedObject(
            source=source,
            mime_type="image/tiff",
            title=title,
            text=describe_scene(scene),
            metadata={
                "raster": {
                    "scene": scene.model_dump(),
                    "tiles": [tile.model_dump() for tile in tiles],
                },
                "locators": [{"file": str(source.path), "asset": title}],
            },
            raw=scene,
        )
