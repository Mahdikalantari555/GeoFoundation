"""Duplicate detection for reviewed examples before export."""

from __future__ import annotations

from collections import Counter
from typing import Any

from geomemory.core.models import DatasetExample


def _example_key(example: DatasetExample) -> tuple[str, str | None]:
    """Return a (task_type, content_signature) key used to identify duplicates.

    The content signature is the sorted JSON of the example's exportable
    payload (the ``payload`` block inside the dataset card).
    """
    card = example.dataset_card or {}
    payload = card.get("payload", {})
    try:
        import json

        sig = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        sig = repr(sorted(payload.items()))
    return (example.task_type, sig)


def find_duplicates(examples: list[DatasetExample]) -> list[list[DatasetExample]]:
    """Group examples that would produce identical export rows.

    Returns a list of groups, each containing two or more examples that are
    duplicates of one another.
    """
    groups: dict[tuple[str, str | None], list[DatasetExample]] = {}
    for example in examples:
        groups.setdefault(_example_key(example), []).append(example)
    return [group for group in groups.values() if len(group) > 1]


def deduplicate_examples(
    examples: list[DatasetExample],
    *,
    keep: str = "newest",
) -> list[DatasetExample]:
    """Deduplicate examples by content, keeping the newest (or oldest) one.

    ``keep`` selects which duplicate survives: ``newest`` (default) keeps the
    example with the latest ``updated_at``; ``oldest`` keeps the earliest.
    """
    if keep not in ("newest", "oldest"):
        raise ValueError(f"keep must be 'newest' or 'oldest', got {keep}")
    groups = find_duplicates(examples)
    unique_ids: set[str] = set()
    for group in groups:
        ordered = sorted(group, key=lambda e: e.updated_at or "", reverse=(keep == "newest"))
        unique_ids.add(ordered[0].id)
    return [e for e in examples if e.id in unique_ids or not _in_duplicate_group(e, groups)]


def _in_duplicate_group(example: DatasetExample, groups: list[list[DatasetExample]]) -> bool:
    return any(any(e.id == example.id for e in group) for group in groups)


def duplicate_counts(examples: list[DatasetExample]) -> Counter[str]:
    """Return the number of examples per task type that have duplicates."""
    counts: Counter[str] = Counter()
    for group in find_duplicates(examples):
        counts[group[0].task_type] += len(group) - 1
    return counts