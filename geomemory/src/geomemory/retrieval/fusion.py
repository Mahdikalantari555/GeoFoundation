"""Reciprocal Rank Fusion and linear fusion."""

from __future__ import annotations

from geomemory.core.models import SearchHit


def rrf_fuse(groups: list[list[SearchHit]], *, top_n: int, k: int = 60) -> list[SearchHit]:
    """Reciprocal Rank Fusion over multiple ranked lists.

    Each hit's fused score is the sum of ``1 / (k + rank + 1)`` across the
    lists in which it appears. Operates on ranks, not raw scores.
    """
    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    seen: dict[str, set[int]] = {}
    for group_idx, group in enumerate(groups):
        for rank, hit in enumerate(group):
            key = hit.id
            if key not in by_id:
                by_id[key] = hit
                seen[key] = set()
            if group_idx not in seen[key]:
                seen[key].add(group_idx)
                scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for key, score in ranked:
        by_id[key].score = score
    return [by_id[k] for k, _ in ranked]


def linear_fuse(
    groups: list[list[SearchHit]],
    *,
    top_n: int,
    weights: list[float] | None = None,
) -> list[SearchHit]:
    """Linear weighted fusion of normalized scores.

    Scores are min-max normalized per list before weighting. If ``weights``
    is None, lists are weighted equally.
    """
    if not groups:
        return []
    if weights is None:
        weights = [1.0 / len(groups)] * len(groups)
    if len(weights) != len(groups):
        raise ValueError("weights must match the number of groups")

    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    for group_idx, group in enumerate(groups):
        if not group:
            continue
        raw = [h.score for h in group]
        lo, hi = min(raw), max(raw)
        span = (hi - lo) or 1.0
        for hit in group:
            norm = (hit.score - lo) / span
            key = hit.id
            if key not in by_id:
                by_id[key] = hit
            scores[key] = scores.get(key, 0.0) + weights[group_idx] * norm
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for key, score in ranked:
        by_id[key].score = score
    return [by_id[k] for k, _ in ranked]