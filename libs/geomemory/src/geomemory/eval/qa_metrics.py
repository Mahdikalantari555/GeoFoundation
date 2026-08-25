"""QA metrics: faithfulness proxy, citation correctness, abstention accuracy."""

from __future__ import annotations

from collections.abc import Iterable

from geomemory.core.models import Citation
from geomemory.qa.abstention import should_abstain
from geomemory.qa.citation import extract_citation_keys


def abstention_accuracy(
    predict_abstain: Iterable[bool],
    expected_abstain: Iterable[bool],
) -> float:
    """Return the fraction of items where abstention matches expectation."""
    pairs = list(zip(predict_abstain, expected_abstain))
    if not pairs:
        return 0.0
    return sum(p == e for p, e in pairs) / len(pairs)


def citation_correctness(
    citations: Iterable[Citation],
    gold_ids: Iterable[str],
) -> float:
    """Return the fraction of citations whose segment is a gold source."""
    gold = set(gold_ids)
    citations = list(citations)
    if not citations:
        return 0.0
    return sum(1 for c in citations if c.segment_id in gold) / len(citations)


def faithfulness_proxy(
    answer_text: str,
    context_ids: Iterable[str],
    gold_ids: Iterable[str] | None = None,
) -> float:
    """Heuristic faithfulness proxy.

    Measures the share of citation keys in the answer that point within the
    provided context. Citation key ``[i]`` references ``context_ids[i-1]``.
    When ``gold_ids`` is given, the share is computed against accepted gold
    sources (a stricter citation-faithfulness estimate).
    """
    context = list(context_ids)
    keys = extract_citation_keys(answer_text)
    if not keys:
        return 0.0
    if gold_ids is not None:
        allowed = set(gold_ids)
        if not allowed:
            return 0.0
    else:
        allowed = set(context)

    valid = 0
    for key in keys:
        idx = key - 1
        target = context[idx] if 0 <= idx < len(context) else None
        if target is not None and target in allowed:
            valid += 1
    return valid / len(keys)


def abstain_rate(answers: Iterable[str]) -> float:
    """Return the fraction of answer texts that signal abstention."""
    texts = list(answers)
    if not texts:
        return 0.0
    return sum(1 for t in texts if should_abstain(t)) / len(texts)
