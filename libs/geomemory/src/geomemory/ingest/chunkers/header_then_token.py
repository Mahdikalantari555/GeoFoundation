"""HeaderThenToken chunker — structural-first chunking with overlap."""

from __future__ import annotations

from typing import Iterable

from geomemory.core.models import ParsedObject, SegmentDraft

_HEADER_RE = {"# ", "## ", "### ", "#### ", "##### ", "###### "}


class HeaderThenTokenChunker:
    """Split a document by header structure, then by token count.

    Headers (Markdown ``#`` lines and standalone ALL-CAPS lines) become chunk
    boundaries. Individual sections are further split when they exceed the
    configured token budget, with configurable overlap. Chunks preserve a
    ``parent_section_id`` (the nearest preceding header) and neighbor ids.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: ParsedObject) -> Iterable[SegmentDraft]:
        sections = _split_sections(document)
        drafts: list[SegmentDraft] = []
        for section in sections:
            section_id = section["id"]
            lines = section["lines"]
            if not lines:
                continue
            joined = "\n".join(lines)
            token_count = _approx_tokens(joined)
            locator = dict(document.metadata.get("locators", [{}])[0] if document.metadata.get("locators") else {})
            if token_count <= self.chunk_size:
                drafts.append(
                    SegmentDraft(
                        text=joined,
                        segment_type="heading" if section["is_header"] else "paragraph",
                        locator={**locator, "section": section["title"]},
                        parent_section_id=section_id,
                    )
                )
            else:
                drafts.extend(
                    _split_long_section(
                        joined,
                        locator=locator,
                        section_id=section_id,
                        section_title=section["title"],
                        chunk_size=self.chunk_size,
                        overlap=self.chunk_overlap,
                    )
                )
        # Assign neighbor ids (relative indices; real ids assigned at persist time).
        for i, draft in enumerate(drafts):
            draft.neighbor_ids = []
            if i > 0:
                draft.neighbor_ids.append(f"prev:{i - 1}")
            if i + 1 < len(drafts):
                draft.neighbor_ids.append(f"next:{i + 1}")
        return drafts


def _split_sections(document: ParsedObject) -> list[dict[str, object]]:
    """Split parsed text into header-delimited sections."""
    sections: list[dict[str, object]] = []
    current: list[str] = []
    current_title = "document"
    current_is_header = False

    def flush() -> None:
        nonlocal current
        if current:
            sections.append(
                {
                    "id": f"sec_{len(sections)}",
                    "title": current_title,
                    "is_header": current_is_header,
                    "lines": list(current),
                }
            )
            current = []

    for line in document.text.splitlines():
        stripped = line.strip()
        is_header = _is_header(stripped)
        if is_header:
            flush()
            current_title = stripped.lstrip("# ").strip()
            current_is_header = True
            current.append(stripped)
        else:
            current.append(line)
    flush()
    if not sections and document.text.strip():
        sections.append(
            {"id": "sec_0", "title": "document", "is_header": False, "lines": document.text.splitlines()}
        )
    return sections


def _is_header(line: str) -> bool:
    if any(line.startswith(h) for h in _HEADER_RE):
        return True
    # ALL-CAPS standalone line heuristic.
    if line and line.isupper() and len(line) > 2 and len(line) < 120:
        return True
    return False


def _split_long_section(
    text: str,
    *,
    locator: dict[str, object],
    section_id: str,
    section_title: str,
    chunk_size: int,
    overlap: int,
) -> list[SegmentDraft]:
    """Split an oversized section on token boundaries with overlap."""
    tokens = text.split()
    drafts: list[SegmentDraft] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = " ".join(tokens[start:end])
        drafts.append(
            SegmentDraft(
                text=chunk_text,
                segment_type="paragraph",
                locator={**locator, "section": section_title, "token_span": [start, end]},
                parent_section_id=section_id,
            )
        )
        if end >= len(tokens):
            break
        start += step
    return drafts


def _approx_tokens(text: str) -> int:
    """Approximate token count from characters (roughly 4 chars/token)."""
    return max(1, len(text) // 4)