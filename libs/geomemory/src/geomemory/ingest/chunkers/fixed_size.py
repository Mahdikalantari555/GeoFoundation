"""FixedSize chunker — token-count fallback chunking with overlap."""

from __future__ import annotations

from collections.abc import Iterable

from geomemory.core.models import ParsedObject, SegmentDraft


class FixedSizeChunker:
    """Split text into fixed-size token windows with configurable overlap.

    This is the fallback chunker used when structural parsing is not
    available or not desired.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document: ParsedObject) -> Iterable[SegmentDraft]:
        tokens = document.text.split()
        if not tokens:
            return []
        step = max(1, self.chunk_size - self.chunk_overlap)
        drafts: list[SegmentDraft] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            drafts.append(
                SegmentDraft(
                    text=" ".join(tokens[start:end]),
                    segment_type="paragraph",
                    locator={"token_span": [start, end]},
                )
            )
            if end >= len(tokens):
                break
            start += step
        for i, draft in enumerate(drafts):
            draft.neighbor_ids = []
            if i > 0:
                draft.neighbor_ids.append(f"prev:{i - 1}")
            if i + 1 < len(drafts):
                draft.neighbor_ids.append(f"next:{i + 1}")
        return drafts
