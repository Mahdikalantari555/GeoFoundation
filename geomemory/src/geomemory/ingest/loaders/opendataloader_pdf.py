"""OpenDataLoader PDF loader — high-quality optional PDF backend."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.loaders.base import java_available, source_bytes


class OpenDataLoaderPdf:
    """Load PDF documents using opendataloader-pdf (requires Java 11+).

    Produces reading-ordered Markdown text plus per-element locators
    ``{page, bbox, element_id, element_type}``. Preferred over
    :class:`PdfLoader` when the ``opendataloader`` extra and a Java runtime
    are available; otherwise the registry falls back to PyMuPDF.
    """

    def supports(self, source: SourceRef) -> bool:
        return bool(source.path and source.path.lower().endswith(".pdf"))

    def load(self, source: SourceRef) -> Iterable[ParsedObject]:
        try:
            import opendataloader_pdf
        except ImportError as exc:
            raise RuntimeError(
                "OpenDataLoaderPdf requires the `opendataloader` extra. "
                "Install with `pip install geomemory[opendataloader]`."
            ) from exc

        if not java_available():
            raise RuntimeError(
                "OpenDataLoaderPdf requires a Java runtime (Java 11+) on PATH."
            )

        input_path, tmpdir = self._materialize(source)
        try:
            opendataloader_pdf.convert(
                input_path=str(input_path),
                format="json",
                output_dir=tmpdir or str(Path(input_path).parent),
                quiet=True,
            )
            output_dir = Path(tmpdir) if tmpdir else Path(input_path).parent
            json_files = list(output_dir.glob("*.json"))
            if not json_files:
                raise RuntimeError("OpenDataLoader produced no JSON output for the PDF")
            data = json.loads(json_files[0].read_text(encoding="utf-8"))
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"OpenDataLoader failed to parse PDF: {exc}") from exc
        finally:
            if tmpdir is not None:
                tmpdir.cleanup()

        kids = data.get("kids", [])
        text = _kids_to_markdown(kids)
        locators = [_kid_to_locator(k) for k in kids]

        yield ParsedObject(
            source=source,
            mime_type="application/pdf",
            title=data.get("title") or (Path(source.path).name if source.path else "Untitled"),
            text=text,
            metadata={
                "loader": "OpenDataLoaderPdf",
                "page_count": data.get("number of pages", 0),
                "locators": locators,
                "odl": data,
            },
        )

    def _materialize(
        self, source: SourceRef
    ) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
        """Return (input_path, tmpdir); tmpdir is None when source.path is reusable."""
        if source.path and Path(source.path).exists():
            return Path(source.path), None
        raw = source_bytes(source)
        tmpdir = tempfile.TemporaryDirectory()
        input_path = Path(tmpdir.name) / "input.pdf"
        input_path.write_bytes(raw)
        return input_path, tmpdir


def _kid_to_locator(kid: dict[str, Any]) -> dict[str, Any]:
    """Extract a minimal citation locator from an ODL element."""
    return {
        "page": kid.get("page number"),
        "bbox": kid.get("bounding box"),
        "element_id": kid.get("id"),
        "element_type": kid.get("type"),
    }


def _kids_to_markdown(kids: list[dict[str, Any]]) -> str:
    """Render ODL elements to reading-ordered Markdown text."""
    blocks: list[str] = []
    for kid in kids:
        kid_type = kid.get("type", "")
        content = kid.get("content", "")
        if not content:
            continue
        if kid_type == "heading":
            level = kid.get("heading level", 1)
            prefix = "#" * max(1, min(6, int(level)))
            blocks.append(f"{prefix} {content}")
        elif kid_type == "list_item":
            blocks.append(f"- {content}")
        else:
            blocks.append(content)
    return "\n\n".join(blocks)
