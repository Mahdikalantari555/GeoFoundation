"""Loader protocol and base utilities."""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from geomemory.core.models import ParsedObject, SourceRef


class Loader(Protocol):
    """Protocol for format-specific loaders."""

    def supports(self, source: SourceRef) -> bool:
        """Return True if this loader can handle the source."""
        ...

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        """Parse the source into one or more ParsedObjects."""
        ...


def source_bytes(source: SourceRef) -> bytes:
    """Return raw bytes for a SourceRef."""
    if source.content_bytes is not None:
        return source.content_bytes
    if source.path is not None:
        return Path(source.path).read_bytes()
    raise ValueError("SourceRef has no local content")


def mime_for_path(path: str) -> str:
    """Map a file extension to a MIME type."""
    suffix = Path(path).suffix.lower()
    table = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".html": "text/html",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".py": "text/x-python",
        ".js": "text/javascript",
        ".ipynb": "application/x-ipynb+json",
        ".csv": "text/csv",
        ".json": "application/json",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".geojson": "application/geo+json",
        ".gpkg": "application/geo+json",
    }
    return table.get(suffix, "application/octet-stream")


def java_available() -> bool:
    """Return True when a `java` executable is on PATH (required by OpenDataLoader)."""
    return shutil.which("java") is not None
