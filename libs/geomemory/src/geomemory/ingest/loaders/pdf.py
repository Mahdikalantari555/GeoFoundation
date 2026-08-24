"""PDF loader with page-level locators."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.loaders.base import source_bytes


class PdfLoader:
    """Load PDF documents with per-page text extraction.

    Uses pymupdf (``fitz``) when available; falls back to raw text if the
    optional dependency is missing (degenerate but non-crashing).
    """

    def supports(self, source: SourceRef) -> bool:
        return bool(source.path and source.path.lower().endswith(".pdf"))

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        raw = source_bytes(source)
        try:
            import fitz  # pymupdf
        except ImportError:
            yield self._fallback(source, raw)
            return

        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as exc:
            # pymupdf is installed but the stream is not a readable PDF
            # (e.g. FileDataError). Degrade to the raw-text fallback.
            yield self._fallback(source, raw, reason=str(exc))
            return
        try:
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            full_text = "\n\n".join(pages)
            yield ParsedObject(
                source=source,
                mime_type="application/pdf",
                title=source.path.split("/")[-1] if source.path else "Untitled",
                text=full_text,
                metadata={
                    "loader": "PdfLoader",
                    "page_count": len(pages),
                    "locators": [{"page": i} for i in range(len(pages))],
                },
            )
        finally:
            doc.close()

    def _fallback(
        self, source: SourceRef, raw: bytes, *, reason: str | None = None
    ) -> ParsedObject:
        text = raw.decode("utf-8", errors="replace")
        metadata: dict[str, Any] = {"loader": "PdfLoader", "fallback": True}
        if reason:
            metadata["fallback_reason"] = reason
        return ParsedObject(
            source=source,
            mime_type="application/pdf",
            title=source.path.split("/")[-1] if source.path else "Untitled",
            text=text,
            metadata=metadata,
        )


class DocxLoader:
    """Load DOCX documents using python-docx."""

    def supports(self, source: SourceRef) -> bool:
        return bool(
            source.path
            and source.path.lower().endswith(".docx")
        )

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        try:
            import docx  # python-docx
        except ImportError:
            yield ParsedObject(
                source=source,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                title=source.path.split("/")[-1] if source.path else "Untitled",
                text=source_bytes(source).decode("utf-8", errors="replace"),
                metadata={"loader": "DocxLoader", "fallback": True},
            )
            return

        document = docx.Document(source.path or source.content_bytes)
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        yield ParsedObject(
            source=source,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            title=source.path.split("/")[-1] if source.path else "Untitled",
            text=text,
            metadata={"loader": "DocxLoader", "paragraph_count": len(paragraphs)},
        )
