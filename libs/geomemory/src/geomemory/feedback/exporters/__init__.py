"""Dataset exporters: transform reviewed examples into JSONL training/eval datasets."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from geomemory.core.models import BenchmarkConfig, DatasetExample
from geomemory.feedback.exporters.dataset_card import build_dataset_card

# Exporters are keyed by task_type. Each returns JSON-serializable row dicts.
Exporter = Callable[[DatasetExample], dict[str, Any]]

_SUPPORTED_TASK_TYPES = ("rag_eval", "qa_eval", "sft", "preference")


def _payload(example: DatasetExample) -> dict[str, Any]:
    card = example.dataset_card or {}
    payload = card.get("payload", {})
    if isinstance(payload, dict):
        return payload
    return {}


def rag_eval_row(example: DatasetExample) -> dict[str, Any]:
    """Row for retrieval evaluation: question + expected relevant ids."""
    p = _payload(example)
    return {
        "question": p.get("question") or p.get("query") or "",
        "expected_documents": p.get("expected_documents", []),
        "gold_ids": p.get("gold_ids", []),
    }


def qa_eval_row(example: DatasetExample) -> dict[str, Any]:
    """Row for QA evaluation: question + reference answer context."""
    p = _payload(example)
    return {
        "question": p.get("question") or p.get("query") or "",
        "reference_answer": p.get("reference_answer") or p.get("answer") or "",
        "expected_documents": p.get("expected_documents", []),
    }


def sft_row(example: DatasetExample) -> dict[str, Any]:
    """Row for supervised fine-tuning: instruction + target answer."""
    p = _payload(example)
    return {
        "instruction": p.get("question") or p.get("instruction") or "",
        "context": p.get("context", []),
        "completion": p.get("answer") or p.get("reference_answer") or "",
    }


def preference_row(example: DatasetExample) -> dict[str, Any]:
    """Row for preference tuning: chose / rejected answers."""
    p = _payload(example)
    return {
        "prompt": p.get("question") or p.get("prompt") or "",
        "chosen": p.get("chosen") or p.get("answer") or "",
        "rejected": p.get("rejected", ""),
    }


_EXPORTERS: dict[str, Exporter] = {
    "rag_eval": rag_eval_row,
    "qa_eval": qa_eval_row,
    "sft": sft_row,
    "preference": preference_row,
}


def supported_task_types() -> tuple[str, ...]:
    """Return the supported task/export types."""
    return _SUPPORTED_TASK_TYPES


def _jsonl_lines(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)


def export_jsonl(
    task_type: str,
    examples: list[DatasetExample],
    output_dir: str | Path,
) -> Path:
    """Export accepted examples for a task type to ``<task_type>.jsonl``.

    A ``<task_type>_card.json`` dataset card is written alongside the rows.
    """
    if task_type not in _EXPORTERS:
        raise ValueError(
            f"Unsupported task type: {task_type}. "
            f"Supported: {', '.join(_SUPPORTED_TASK_TYPES)}"
        )
    if not examples:
        raise ValueError(f"No accepted examples for task type: {task_type}")

    exporter = _EXPORTERS[task_type]
    rows = [exporter(e) for e in examples]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines_path = out_dir / f"{task_type}.jsonl"
    lines_path.write_text(_jsonl_lines(rows) + "\n", encoding="utf-8")

    card = build_dataset_card(task_type=task_type, count=len(rows))
    card_path = out_dir / f"{task_type}_card.json"
    # Serialize without the config block (benchmark config is not used here).
    card_dict = {
        "task_type": card["task_type"],
        "description": card["description"],
        "count": card["count"],
        "created_at": card["created_at"],
        "columns": card["columns"],
    }
    card_path.write_text(json.dumps(card_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    return lines_path


def export_benchmark_jsonl(
    rows: list[dict[str, Any]],
    task_type: str,
    output_dir: str | Path,
    *,
    config: BenchmarkConfig | None = None,
) -> Path:
    """Write raw benchmark rows (used by the eval runner) to disk."""
    if not rows:
        raise ValueError("No rows to export")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{task_type}.jsonl"
    path.write_text(_jsonl_lines(rows) + "\n", encoding="utf-8")
    if config is not None:
        config_path = out_dir / f"{task_type}_config.json"
        config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return path
