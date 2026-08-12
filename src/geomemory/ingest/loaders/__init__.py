"""Loader registry and built-in loaders."""

from __future__ import annotations

from geomemory.core.models import SourceRef
from geomemory.core.plugin_registry import LoaderRegistry
from geomemory.ingest.loaders.base import Loader, mime_for_path
from geomemory.ingest.loaders.code import CodeLoader, NotebookLoader
from geomemory.ingest.loaders.geojson import GeoJsonLoader
from geomemory.ingest.loaders.geotiff import GeoTiffLoader
from geomemory.ingest.loaders.pdf import DocxLoader, PdfLoader
from geomemory.ingest.loaders.text import TextLoader


def default_registry() -> LoaderRegistry:
    """Return a registry with the built-in loaders registered by mime type."""
    registry = LoaderRegistry()
    for mime in ("text/plain", "text/markdown", "text/html"):
        registry.register(mime, TextLoader())
    registry.register("application/pdf", PdfLoader())
    registry.register(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DocxLoader(),
    )
    registry.register("text/x-python", CodeLoader())
    registry.register("text/javascript", CodeLoader())
    registry.register("application/x-ipynb+json", NotebookLoader())
    for mime in ("image/tiff", "image/geotiff"):
        registry.register(mime, GeoTiffLoader())
    registry.register("application/geo+json", GeoJsonLoader())
    return registry


def get_loader(source: SourceRef, registry: LoaderRegistry | None = None) -> Loader | None:
    """Resolve a loader for a source, falling back to extension matching."""
    registry = registry or default_registry()
    if source.path is not None:
        mime = mime_for_path(source.path)
        loader = registry.get(mime)
        if loader is not None:
            return loader
        # Extension-based fallback for loaders not keyed by mime.
        suffix = source.path.lower()
        if suffix.endswith((".py", ".js", ".mjs", ".gee")):
            return registry.get("text/x-python") or registry.get("text/javascript")
        if suffix.endswith(".ipynb"):
            return registry.get("application/x-ipynb+json")
        if suffix.endswith(".pdf"):
            return registry.get("application/pdf")
        if suffix.endswith(".docx"):
            return registry.get(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        if suffix.endswith((".tif", ".tiff")):
            return registry.get("image/tiff") or registry.get("image/geotiff")
        if suffix.endswith((".geojson", ".gpkg")):
            return registry.get("application/geo+json")
    for loader in registry.all().values():
        if loader.supports(source):
            return loader
    return None


__all__ = [
    "CodeLoader",
    "DocxLoader",
    "GeoJsonLoader",
    "GeoTiffLoader",
    "Loader",
    "LoaderRegistry",
    "NotebookLoader",
    "PdfLoader",
    "TextLoader",
    "default_registry",
    "get_loader",
    "mime_for_path",
]