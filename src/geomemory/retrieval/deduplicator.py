"""Result deduplication and diversity enforcement."""

from __future__ import annotations

from collections import Counter
from typing import Callable

from geomemory.core.models import SearchHit


def deduplicate(hits: list[SearchHit]) -> list[SearchHit]:
    """Remove duplicate hits by id, keeping the first occurrence."""
    seen: set[str] = set()
    result: list[SearchHit] = []
    for hit in hits:
        if hit.id not in seen:
            seen.add(hit.id)
            result.append(hit)
    return result


def enforce_diversity(
    hits: list[SearchHit],
    *,
    max_per_document: int = 3,
    key_fn: Callable[[SearchHit], str] | None = None,
) -> list[SearchHit]:
    """Limit the number of hits per parent document/section.

    ``key_fn`` extracts a grouping key from a hit (default: the revision_id
    in metadata, falling back to the hit id).
    """
    if key_fn is None:
        key_fn = lambda hit: str(hit.metadata.get("revision_id", hit.id))  # noqa: E731

    counts: Counter[str] = Counter()
    result: list[SearchHit] = []
    for hit in hits:
        key = key_fn(hit)
        if counts[key] < max_per_document:
            counts[key] += 1
            result.append(hit)
    return result