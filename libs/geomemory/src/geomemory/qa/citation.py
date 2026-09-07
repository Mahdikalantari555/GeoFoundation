"""Citation mapping and validation."""

from __future__ import annotations

import re

from geomemory.core.models import Citation, SearchHit

_CITE_RE = re.compile(r"\[(\d+)\]")


def extract_citation_keys(text: str) -> list[int]:
    """Extract citation keys like [1], [2] from an answer text."""
    return [int(m) for m in _CITE_RE.findall(text)]


def map_citations(
    answer_id: str,
    answer_text: str,
    sources: list[SearchHit],
) -> list[Citation]:
    """Map citation keys in the answer to source segments.

    Citation key ``[i]`` refers to ``sources[i-1]``. Keys out of range are
    ignored. Returns a list of Citation models.
    """
    citations: list[Citation] = []
    keys = extract_citation_keys(answer_text)
    for key in keys:
        idx = key - 1
        if 0 <= idx < len(sources):
            hit = sources[idx]
            citations.append(
                Citation(
                    answer_id=answer_id,
                    segment_id=hit.id,
                    locator=hit.locator,
                )
            )
    return citations


def validate_citations(citations: list[Citation], sources: list[SearchHit]) -> bool:
    """Return True if all citations reference a known source segment."""
    source_ids = {h.id for h in sources}
    return all(c.segment_id in source_ids for c in citations)
