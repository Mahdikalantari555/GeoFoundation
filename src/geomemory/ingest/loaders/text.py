"""TXT and Markdown loaders."""

from __future__ import annotations

from typing import Iterable

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.loaders.base import mime_for_path, source_bytes

_TEXT_MIMES = {"text/plain", "text/markdown", "text/html"}


class TextLoader:
    """Load plain text, Markdown, and simple HTML documents."""

    def supports(self, source: SourceRef) -> bool:
        if source.path is not None:
            return mime_for_path(source.path) in _TEXT_MIMES
        return source.content_bytes is not None

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        raw = source_bytes(source)
        text = raw.decode("utf-8", errors="replace")
        mime = mime_for_path(source.path) if source.path else "text/plain"
        title = source.path.split("/")[-1] if source.path else "Untitled"
        yield ParsedObject(
            source=source,
            mime_type=mime,
            title=title,
            text=text,
            metadata={"loader": "TextLoader"},
        )