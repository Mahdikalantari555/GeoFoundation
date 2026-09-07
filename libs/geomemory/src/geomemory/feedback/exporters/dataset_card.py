"""Dataset card generation for exported datasets."""

from __future__ import annotations

from typing import Any

from geomemory.core.models import utc_now

_TASK_DESCRIPTIONS: dict[str, str] = {
    "rag_eval": "Retrieval evaluation examples: question-to-gold-document pairs.",
    "qa_eval": "QA evaluation examples: question, reference answer, expected sources.",
    "sft": "Supervised fine-tuning examples: instruction/context to completion.",
    "preference": "Preference tuning examples: chosen vs rejected answers.",
}

_TASK_COLUMNS: dict[str, list[str]] = {
    "rag_eval": ["question", "expected_documents", "gold_ids"],
    "qa_eval": ["question", "reference_answer", "expected_documents"],
    "sft": ["instruction", "context", "completion"],
    "preference": ["prompt", "chosen", "rejected"],
}


def build_dataset_card(
    *,
    task_type: str,
    count: int,
    description: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a dataset card describing an exported dataset.

    The card captures the task type, row count, description, column layout,
    creation time, and any caller-supplied provenance fields.
    """
    if task_type not in _TASK_DESCRIPTIONS:
        raise ValueError(f"Unsupported task type: {task_type}")
    return {
        "task_type": task_type,
        "description": description or _TASK_DESCRIPTIONS[task_type],
        "count": count,
        "columns": _TASK_COLUMNS[task_type],
        "created_at": utc_now(),
        **extra,
    }
