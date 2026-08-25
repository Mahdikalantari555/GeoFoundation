"""Tests for retrieval fusion: RRF and linear fusion."""

from __future__ import annotations

from geomemory.core.models import SearchHit
from geomemory.retrieval.fusion import linear_fuse, rrf_fuse


def _hits(ids: list[str]) -> list[SearchHit]:
    return [SearchHit(id=i, score=float(score)) for score, i in enumerate(reversed(ids), start=1)]


class TestRrfFuse:
    def test_common_item_ranks_first(self):
        a = _hits(["d1", "d2", "d3"])
        b = _hits(["d2", "d1", "d4"])
        fused = rrf_fuse([a, b], top_n=3)
        assert fused[0].id == "d2"  # rank 2 in both lists
        assert fused[0].score > 0.0

    def test_top_n_limits_results(self):
        a = _hits(["d1", "d2", "d3"])
        b = _hits(["d4", "d5", "d6"])
        fused = rrf_fuse([a, b], top_n=2)
        assert len(fused) == 2

    def test_empty_groups(self):
        assert rrf_fuse([], top_n=5) == []


class TestLinearFuse:
    def test_weighted_scores(self):
        a = _hits(["d1", "d2"])
        b = _hits(["d2", "d3"])
        fused = linear_fuse([a, b], top_n=3, weights=[0.5, 0.5])
        assert fused[0].id == "d2"

    def test_weights_must_match_groups(self):
        a = _hits(["d1"])
        try:
            linear_fuse([a], top_n=1, weights=[0.5, 0.5])
        except ValueError:
            return
        raise AssertionError("expected ValueError for mismatched weights")

    def test_single_group_passthrough(self):
        a = _hits(["d1", "d2"])
        fused = linear_fuse([a], top_n=2)
        assert fused[0].id == "d1"
