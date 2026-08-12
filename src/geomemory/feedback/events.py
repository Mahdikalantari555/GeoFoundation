"""Feedback event model helpers and validation.

Feedback events are append-only raw records. They are not training data until
they have been explicitly reviewed and promoted into ``DatasetExample`` rows.
This module provides factories for common feedback labels and the translation
from raw events to reviewable examples.
"""

from __future__ import annotations

from typing import Any

from geomemory.core.models import DatasetExample, FeedbackEvent


class FeedbackLabels:
    """Canonical feedback label constants recorded in ``FeedbackEvent.label``."""

    ANSWER_RATING = "answer_rating"
    SOURCE_RELEVANCE = "source_relevance"
    EDITED_ANSWER = "edited_answer"
    PREFERRED_SOURCES = "preferred_source_ids"
    CITATION_CORRECTNESS = "citation_correctness"


def answer_rating(
    target_id: str,
    rating: int,
    *,
    actor: str = "user",
    payload: dict[str, Any] | None = None,
) -> FeedbackEvent:
    """Create an immutable answer-rating event for an answer entity."""
    if not 1 <= rating <= 5:
        raise ValueError(f"rating must be in 1..5, got {rating}")
    return FeedbackEvent(
        target_type="answer",
        target_id=target_id,
        actor=actor,
        label=FeedbackLabels.ANSWER_RATING,
        payload={"rating": rating, **(payload or {})},
    )


def source_relevance(
    target_id: str,
    relevant: bool,
    *,
    actor: str = "user",
    payload: dict[str, Any] | None = None,
) -> FeedbackEvent:
    """Create a source-relevance event for a segment or source id."""
    return FeedbackEvent(
        target_type="segment",
        target_id=target_id,
        actor=actor,
        label=FeedbackLabels.SOURCE_RELEVANCE,
        payload={"relevant": bool(relevant), **(payload or {})},
    )


def edited_answer(
    target_id: str,
    edited_text: str,
    *,
    original_text: str = "",
    actor: str = "user",
    payload: dict[str, Any] | None = None,
) -> FeedbackEvent:
    """Create an edited-answer event recording an improved version."""
    if not edited_text.strip():
        raise ValueError("edited_text must not be empty")
    return FeedbackEvent(
        target_type="answer",
        target_id=target_id,
        actor=actor,
        label=FeedbackLabels.EDITED_ANSWER,
        payload={"edited_text": edited_text, "original_text": original_text, **(payload or {})},
    )


def preferred_sources(
    target_id: str,
    preferred_ids: list[str],
    *,
    actor: str = "user",
    payload: dict[str, Any] | None = None,
) -> FeedbackEvent:
    """Create a preferred-sources event recording which segments were preferred."""
    if not preferred_ids:
        raise ValueError("preferred_ids must not be empty")
    return FeedbackEvent(
        target_type="answer",
        target_id=target_id,
        actor=actor,
        label=FeedbackLabels.PREFERRED_SOURCES,
        payload={"preferred_source_ids": list(preferred_ids), **(payload or {})},
    )


def build_dataset_example(
    task_type: str,
    source_feedback: list[FeedbackEvent] | None = None,
    **payload: Any,
) -> DatasetExample:
    """Build a pending ``DatasetExample`` from source feedback events.

    ``payload`` is embedded into the example as exportable content (e.g. the
    question, context, answer, label). Source feedback ids are referenced for
    provenance and are not copied into the example body.
    """
    source_ids = [e.id for e in source_feedback] if source_feedback else []
    return DatasetExample(
        task_type=task_type,
        source_feedback_ids=source_ids,
        dataset_card={
            "payload_keys": sorted(payload.keys()),
            "payload": payload,
        },
    )


def feedback_helpers() -> dict[str, str]:
    """Return the canonical label constants for reference and validation."""
    return {
        "answer_rating": FeedbackLabels.ANSWER_RATING,
        "source_relevance": FeedbackLabels.SOURCE_RELEVANCE,
        "edited_answer": FeedbackLabels.EDITED_ANSWER,
        "preferred_sources": FeedbackLabels.PREFERRED_SOURCES,
    }