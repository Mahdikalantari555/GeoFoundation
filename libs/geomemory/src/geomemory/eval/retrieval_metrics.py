"""Retrieval metrics: Recall@K, MRR, nDCG, Precision.

All functions operate on an unordered set of relevant ids and an ordered
retrieved id list. Rank is 1-based.
"""

from __future__ import annotations

import math
from typing import Iterable


def recall_at_k(relevant: Iterable[str], retrieved: list[str], k: int | None = None) -> float:
    """Return the fraction of relevant ids retrieved within the top ``k``."""
    gold = set(relevant)
    if not gold:
        return 0.0
    top = retrieved if k is None else retrieved[:k]
    return len(gold & set(top)) / len(gold)


def precision_at_k(relevant: Iterable[str], retrieved: list[str], k: int | None = None) -> float:
    """Return the fraction of top-``k`` retrieved ids that are relevant."""
    gold = set(relevant)
    if not gold:
        return 0.0
    top = retrieved if k is None else retrieved[:k]
    if not top:
        return 0.0
    return len(gold & set(top)) / len(top)


def mrr_at_k(relevant: Iterable[str], retrieved: list[str], k: int | None = None) -> float:
    """Return the reciprocal rank of the first relevant result within top ``k``."""
    gold = set(relevant)
    if not gold:
        return 0.0
    top = retrieved if k is None else retrieved[:k]
    for rank, rid in enumerate(top, start=1):
        if rid in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(relevant: Iterable[str], retrieved: list[str], k: int | None = None) -> float:
    """Return the normalized discounted cumulative gain at ``k``.

    Gain is 1 for relevant ids, 0 otherwise; ideal DCG is over the same
    number of gold ids, capped at ``k``.
    """
    gold = set(relevant)
    if not gold:
        return 0.0
    top = retrieved if k is None else retrieved[:k]
    if not top:
        return 0.0

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(top, start=1)
        if rid in gold
    )
    ideal_len = min(len(gold), len(top))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_len + 1))
    return dcg / idcg if idcg > 0 else 0.0