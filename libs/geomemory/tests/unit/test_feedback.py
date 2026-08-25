"""Tests for the feedback pipeline: events, review queue, dedup, exporters."""

from __future__ import annotations

import pytest

from geomemory.feedback.dedup import deduplicate_examples, find_duplicates
from geomemory.feedback.events import (
    FeedbackLabels,
    answer_rating,
    build_dataset_example,
    edited_answer,
    preferred_sources,
    source_relevance,
)
from geomemory.feedback.exporters import (
    export_jsonl,
    preference_row,
    qa_eval_row,
    rag_eval_row,
    sft_row,
    supported_task_types,
)
from geomemory.feedback.review_queue import ReviewQueue
from geomemory.storage.repositories.feedback_repo import (
    DatasetExampleRepository,
)


class TestEvents:
    def test_answer_rating_event(self):
        ev = answer_rating("ans-1", rating=4)
        assert ev.label == FeedbackLabels.ANSWER_RATING
        assert ev.payload["rating"] == 4

    def test_answer_rating_validation(self):
        with pytest.raises(ValueError):
            answer_rating("ans-1", rating=0)

    def test_source_relevance_event(self):
        ev = source_relevance("seg-1", relevant=True)
        assert ev.label == FeedbackLabels.SOURCE_RELEVANCE
        assert ev.payload["relevant"] is True

    def test_edited_answer_event(self):
        ev = edited_answer("ans-1", "improved text", original_text="old")
        assert ev.payload["edited_text"] == "improved text"
        assert ev.payload["original_text"] == "old"

    def test_preferred_sources_event(self):
        ev = preferred_sources("ans-1", ["s1", "s2"])
        assert ev.payload["preferred_source_ids"] == ["s1", "s2"]

    def test_build_example_embeds_payload(self):
        ex = build_dataset_example(
            task_type="qa_eval", question="q?", reference_answer="a", gold_ids=["s1"]
        )
        assert ex.task_type == "qa_eval"
        assert ex.review_state == "pending"
        assert ex.dataset_card["payload"]["question"] == "q?"


class TestReviewQueue:
    def test_accept_and_reject(self, temp_workspace):
        example = build_dataset_example(task_type="qa_eval")
        DatasetExampleRepository(temp_workspace.conn).create(example)
        q = ReviewQueue(temp_workspace.conn)
        assert q.review(example.id, True) is True
        assert q.get(example.id).review_state == "accepted"
        assert q.reject(example.id) is True
        assert q.get(example.id).review_state == "rejected"

    def test_accept_missing(self, temp_workspace):
        q = ReviewQueue(temp_workspace.conn)
        assert q.review("missing", True) is False


class TestExporters:
    def test_rag_eval_row(self):
        ex = build_dataset_example(
            task_type="rag_eval", question="q", gold_ids=["s1", "s2"]
        )
        row = rag_eval_row(ex)
        assert row["gold_ids"] == ["s1", "s2"]

    def test_qa_eval_row(self):
        ex = build_dataset_example(
            task_type="qa_eval", question="q", reference_answer="ans"
        )
        row = qa_eval_row(ex)
        assert row["reference_answer"] == "ans"

    def test_sft_row(self):
        ex = build_dataset_example(
            task_type="sft", question="q", answer="a", context=["ctx"]
        )
        row = sft_row(ex)
        assert row["instruction"] == "q"
        assert row["completion"] == "a"

    def test_preference_row(self):
        ex = build_dataset_example(task_type="preference", question="q", chosen="good", rejected="bad")
        row = preference_row(ex)
        assert row["chosen"] == "good"
        assert row["rejected"] == "bad"

    def test_export_jsonl_writes_lines_and_card(self, temp_workspace, tmp_path):
        ex = build_dataset_example(task_type="qa_eval", question="q", answer="a")
        DatasetExampleRepository(temp_workspace.conn).create(ex)
        path = export_jsonl("qa_eval", [ex], tmp_path)
        assert path.name == "qa_eval.jsonl"
        assert path.read_text(encoding="utf-8").strip()
        assert (tmp_path / "qa_eval_card.json").is_file()

    def test_supported_task_types(self):
        assert "rag_eval" in supported_task_types()


class TestDedup:
    def test_dedup_keeps_newest(self):
        ex1 = build_dataset_example(task_type="qa_eval", question="same", answer="a")
        ex2 = build_dataset_example(task_type="qa_eval", question="same", answer="a")
        ex1.updated_at = "2020-01-01T00:00:00"
        ex2.updated_at = "2021-01-01T00:00:00"
        unique = deduplicate_examples([ex1, ex2], keep="newest")
        assert len(unique) == 1
        assert unique[0].id == ex2.id

    def test_dedup_groups_duplicates(self):
        ex1 = build_dataset_example(task_type="qa_eval", question="same", answer="a")
        ex2 = build_dataset_example(task_type="qa_eval", question="same", answer="a")
        groups = find_duplicates([ex1, ex2])
        assert len(groups) == 1
