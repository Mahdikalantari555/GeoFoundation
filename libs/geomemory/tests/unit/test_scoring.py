"""Unit tests for MemoryScorer rule-based scoring."""

from __future__ import annotations

import pytest

from geomemory.feedback.scoring import MemoryScorer


@pytest.fixture()
def scorer() -> MemoryScorer:
    return MemoryScorer()


# ── base score ────────────────────────────────────────────────────────────────


class TestBaseScore:
    def test_default_base_is_5(self, scorer):
        assert scorer.score() == 5.0

    def test_custom_base(self, scorer):
        assert scorer.score(base=10.0) == 10.0


# ── confirming signals ────────────────────────────────────────────────────────


class TestConfirming:
    def test_no_confirmations(self, scorer):
        assert scorer.score(confirming=0) == 5.0

    def test_one_confirmation(self, scorer):
        assert scorer.score(confirming=1) == 8.0

    def test_two_confirmations(self, scorer):
        assert scorer.score(confirming=2) == 11.0

    def test_three_confirmations_caps_at_plus_6(self, scorer):
        # 3 * 3 = 9, cap is 6 → +6
        assert scorer.score(confirming=3) == 11.0

    def test_six_confirmations(self, scorer):
        assert scorer.score(confirming=6) == 11.0


# ── retrieval usage ───────────────────────────────────────────────────────────


class TestRetrievalUsage:
    def test_no_usage(self, scorer):
        assert scorer.score(retrieval_usage=0) == 5.0

    def test_one_usage(self, scorer):
        assert scorer.score(retrieval_usage=1) == 7.0

    def test_two_usages_caps_at_plus_4(self, scorer):
        assert scorer.score(retrieval_usage=2) == 9.0

    def test_five_usages(self, scorer):
        assert scorer.score(retrieval_usage=5) == 9.0


# ── multiple-actors bonus ─────────────────────────────────────────────────────


class TestMultipleActors:
    def test_false_adds_nothing(self, scorer):
        assert scorer.score(multiple_actors=False) == 5.0

    def test_true_adds_3(self, scorer):
        assert scorer.score(multiple_actors=True) == 8.0

    def test_combined_with_confirmations(self, scorer):
        # base 5 + 3 (one confirm) + 3 (multiple actors) = 11
        assert scorer.score(confirming=1, multiple_actors=True) == 11.0


# ── rejections ────────────────────────────────────────────────────────────────


class TestRejections:
    def test_one_rejection(self, scorer):
        assert scorer.score(rejections=1) == 0.0  # 5 - 5 = 0, clamped

    def test_one_rejection_from_higher_base(self, scorer):
        assert scorer.score(base=10, rejections=1) == 5.0

    def test_two_rejections_below_zero_clamp(self, scorer):
        assert scorer.score(base=10, rejections=2) == 0.0

    def test_rejections_with_confirmations(self, scorer):
        # base 5 + 6 (2 confirm) - 5 (1 reject) = 6
        assert scorer.score(confirming=2, rejections=1) == 6.0


# ── contradictions ────────────────────────────────────────────────────────────


class TestContradictions:
    def test_one_contradiction(self, scorer):
        assert scorer.score(contradictions=1) == 2.0

    def test_two_contradictions_clamp(self, scorer):
        assert scorer.score(contradictions=2) == 0.0


# ── combined signals ──────────────────────────────────────────────────────────


class TestCombined:
    def test_all_positive(self, scorer):
        # base 5 + 6 (2 confirm) + 4 (2 usage) + 3 (multi) = 18
        result = scorer.score(
            confirming=2, retrieval_usage=2, multiple_actors=True
        )
        assert result == 18.0

    def test_mixed_positive_negative(self, scorer):
        # base 5 + 3 (1 confirm) - 5 (1 reject) = 3
        result = scorer.score(confirming=1, rejections=1)
        assert result == 3.0


# ── clamping ──────────────────────────────────────────────────────────────────


class TestClamping:
    def test_lower_clamp_at_zero(self, scorer):
        result = scorer.score(base=0, rejections=10)
        assert result == 0.0

    def test_upper_cap_at_twenty(self, scorer):
        # base 5 + 6 confirm + 4 usage + 3 multi + large confirm cap = 18 max
        result = scorer.score(
            base=20, confirming=10, retrieval_usage=10, multiple_actors=True
        )
        assert result == 20.0


# ── state thresholds ──────────────────────────────────────────────────────────


class TestStateFor:
    def test_proposed_below_eight(self, scorer):
        assert scorer.state_for(7.0) == "proposed"
        assert scorer.state_for(0.0) == "proposed"

    def test_supported_at_eight_through_thirteen(self, scorer):
        assert scorer.state_for(8.0) == "supported"
        assert scorer.state_for(13.0) == "supported"

    def test_verified_at_fourteen_and_above(self, scorer):
        assert scorer.state_for(14.0) == "verified"
        assert scorer.state_for(20.0) == "verified"

    def test_boundary_seventeen_point_nine(self, scorer):
        assert scorer.state_for(17.9) == "verified"


# ── compute_from_payload ──────────────────────────────────────────────────────


class TestComputeFromPayload:
    def test_empty_payload(self, scorer):
        assert scorer.compute_from_payload({}) == 5.0

    def test_with_signals(self, scorer):
        result = scorer.compute_from_payload({"confirming": 2, "rejections": 1})
        assert result == 6.0  # 5 + 6 - 5 = 6

    def test_multiple_actors_in_payload(self, scorer):
        result = scorer.compute_from_payload({"multiple_actors": True})
        assert result == 8.0

    def test_invalid_types_coerced(self, scorer):
        result = scorer.compute_from_payload({"confirming": "2", "rejections": "1"})
        assert result == 6.0


# ── weight_for_state ──────────────────────────────────────────────────────────


class TestWeightForState:
    def test_verified_weight(self, scorer):
        assert scorer.weight_for_state("verified") == 0.8

    def test_supported_weight(self, scorer):
        assert scorer.weight_for_state("supported") == 0.4

    def test_proposed_weight(self, scorer):
        assert scorer.weight_for_state("proposed") == 0.1

    def test_unknown_state_defaults(self, scorer):
        assert scorer.weight_for_state("missing") == 0.1
