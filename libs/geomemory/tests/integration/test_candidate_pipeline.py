"""Integration tests for the feedback → candidate promotion pipeline."""

from __future__ import annotations

import pytest

from geomemory.core.models import FeedbackEvent
from geomemory.services.candidate_memory_service import CandidateMemoryService
from geomemory.services.feedback_service import FeedbackService


@pytest.fixture()
def svc(temp_workspace):
    return FeedbackService(temp_workspace.conn)


@pytest.fixture()
def cm_svc(temp_workspace):
    return CandidateMemoryService(temp_workspace.conn)


class TestPromoteToCandidate:
    def test_creates_candidate_with_correct_score(self, svc):
        event = FeedbackEvent(
            target_type="answer",
            target_id="ans_1",
            label="answer_rating",
            payload={"rating": 5},
        )
        stored = svc.record_feedback(event)
        promoted = svc.promote_to_candidate([stored.id], "NDVI indicates vegetation health")
        assert promoted is not None
        assert promoted.state == "supported"  # 1 confirm → score 8
        assert promoted.confidence_score == 8.0
        assert stored.id in promoted.source_feedback_ids

    def test_candidate_content_stored(self, svc):
        event = FeedbackEvent(target_type="answer", target_id="ans_x", label="answer_rating")
        stored = svc.record_feedback(event)
        promoted = svc.promote_to_candidate([stored.id], "correction text here")
        assert promoted.content == "correction text here"

    def test_multiple_events_boost_score(self, svc):
        events = [
            svc.record_feedback(
                FeedbackEvent(target_type="answer", target_id="ans_1", label="answer_rating")
            )
            for _ in range(3)
        ]
        promoted = svc.promote_to_candidate([e.id for e in events], "robust fact")
        # 3 confirmations → min(3*3, 6) = 6 → base 5 + 6 = 11 → supported
        assert promoted.confidence_score == 11.0
        assert promoted.state == "supported"
        assert len(promoted.source_feedback_ids) == 3


class TestScoreUpdatesState:
    def test_single_signal_updates_score(self, cm_svc):
        cm = cm_svc.create("some fact", memory_type="fact")
        assert cm.state == "proposed"
        assert cm.confidence_score == 5.0

        new_score = cm_svc.score(cm.id, {"confirming": 2})
        refreshed = cm_svc.get(cm.id)
        assert refreshed.confidence_score == new_score
        assert refreshed.state == "supported"  # 5 + 6 = 11 ≥ 8

    def test_rejection_drops_state(self, cm_svc):
        # Start at verified (score 14: base 5 + 6 confirm cap + 3 multi)
        cm = cm_svc.create("strong fact", memory_type="fact")
        cm_svc.score(cm.id, {"confirming": 5, "multiple_actors": True})
        assert cm_svc.get(cm.id).state == "verified"

        # Apply rejection while keeping previous confirmations: -5 → score 9 → supported
        cm_svc.score(cm.id, {"confirming": 5, "multiple_actors": True, "rejections": 1})
        refreshed = cm_svc.get(cm.id)
        assert refreshed.state == "supported"
        assert refreshed.confidence_score == 9.0

    def test_double_rejection_clamps_and_drops(self, cm_svc):
        cm = cm_svc.create("supported fact", memory_type="fact")
        cm_svc.score(cm.id, {"confirming": 2})  # score 11, supported
        assert cm_svc.get(cm.id).state == "supported"

        # Two rejections (-10) from base 5 → clamped to 0, state drops to proposed
        cm_svc.score(cm.id, {"rejections": 2})
        refreshed = cm_svc.get(cm.id)
        assert refreshed.state == "proposed"
        assert refreshed.confidence_score == 0.0

    def test_multi_actor_bonus_applied(self, cm_svc):
        cm = cm_svc.create("community fact", memory_type="fact")
        # Base 5 + 3 (one confirm) + 3 (multi actors) = 11
        new_score = cm_svc.score(cm.id, {"confirming": 1, "multiple_actors": True})
        refreshed = cm_svc.get(cm.id)
        assert refreshed.confidence_score == new_score
        assert refreshed.state == "supported"


class TestStateTransitionsAcrossPipeline:
    def test_full_lifecycle_proposed_to_verified(self, cm_svc):
        cm = cm_svc.create("initial hypothesis", memory_type="fact")
        assert cm.state == "proposed"

        # First confirmation → supported
        cm_svc.score(cm.id, {"confirming": 1})
        assert cm_svc.get(cm.id).state == "supported"

        # More confirmations + multi-actor → verified
        cm_svc.score(cm.id, {"confirming": 3, "multiple_actors": True})
        assert cm_svc.get(cm.id).state == "verified"

    def test_rejection_at_any_stage(self, cm_svc):
        cm = cm_svc.create("contested claim", memory_type="fact")
        cm_svc.score(cm.id, {"confirming": 2})  # score 11, supported
        assert cm_svc.get(cm.id).state == "supported"

        cm_svc.score(cm.id, {"rejections": 1})  # score 6, proposed
        assert cm_svc.get(cm.id).state == "proposed"

        # Rejection from any state still works
        cm_svc.promote(cm.id, "rejected", "moderator", "overturned")
        assert cm_svc.get(cm.id).state == "rejected"
