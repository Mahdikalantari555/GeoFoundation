"""GeoJSON/GeoPackage loader — produces a searchable vector layer description."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.rs.vector.reader import VectorReader, describe_layer


class GeoJsonLoader:
    """Load vector files (GeoJSON, GeoPackage) into a searchable layer payload."""

    def __init__(self, *, reader: VectorReader | None = None) -> None:
        self.reader = reader or VectorReader()

    def supports(self, source: SourceRef) -> bool:
        """Return True for GeoJSON/GeoPackage files (by extension)."""
        if source.path is None:
            return False
        return Path(source.path).suffix.lower() in (".geojson", ".gpkg")

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        """Read layer metadata and yield a single ParsedObject."""
        if source.path is None:
            raise ValueError("GeoJsonLoader requires a local file path")
        layer = self.reader.read_layer(source.path)
        title = Path(source.path).name
        yield ParsedObject(
            source=source,
            mime_type="application/geo+json",
            title=title,
            text=describe_layer(layer),
            metadata={
                "vector": {"layer": layer.model_dump()},
                "locators": [{"file": str(source.path), "asset": title}],
            },
            raw=layer,
        )
