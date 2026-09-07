"""Token-budget-aware context assembly for QA."""

from __future__ import annotations

from geomemory.core.models import SearchHit


def estimate_tokens(text: str) -> int:
    """Approximate token count (roughly 4 chars per token)."""
    return max(1, len(text) // 4)


def pack_context(
    hits: list[SearchHit],
    *,
    token_budget: int = 2000,
    per_hit_budget: int = 500,
) -> list[SearchHit]:
    """Select hits that fit within a token budget.

    Hits are assumed to be pre-ranked. Each hit's text is truncated to
    ``per_hit_budget`` tokens; the total must stay within ``token_budget``.
    """
    selected: list[SearchHit] = []
    used = 0
    for hit in hits:
        text = hit.text
        tokens = estimate_tokens(text)
        if tokens > per_hit_budget:
            # Truncate to the per-hit budget.
            chars = per_hit_budget * 4
            text = text[:chars]
            tokens = per_hit_budget
        if used + tokens > token_budget:
            break
        hit.text = text
        selected.append(hit)
        used += tokens
    return selected


def format_context(hits: list[SearchHit]) -> str:
    """Format hits into a numbered context block for a prompt."""
    blocks: list[str] = []
    for i, hit in enumerate(hits, start=1):
        locator = hit.locator or {}
        loc_str = ", ".join(f"{k}={v}" for k, v in locator.items()) or "unknown"
        blocks.append(f"[{i}] (source: {loc_str})\n{hit.text}")
    return "\n\n".join(blocks)
