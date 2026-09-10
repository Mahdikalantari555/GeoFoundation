"""Unit tests for CandidateMemoryRepository state transitions."""

from __future__ import annotations

import time

import pytest

from geomemory.core.models import CandidateMemory
from geomemory.feedback.candidate_memory import CandidateMemoryRepository


@pytest.fixture()
def repo(temp_workspace) -> CandidateMemoryRepository:
    return CandidateMemoryRepository(temp_workspace.conn)


@pytest.fixture()
def make_candidate(repo: CandidateMemoryRepository):
    def _make(state: str = "proposed", score: float = 5.0) -> CandidateMemory:
        cm = CandidateMemory(
            content="test content", memory_type="fact", state=state, confidence_score=score
        )
        return repo.create(cm)
    return _make


# ── create / get / list / search ──────────────────────────────────────────────


class TestCRUD:
    def test_create_returns_candidate(self, repo):
        cm = CandidateMemory(content="hello")
        created = repo.create(cm)
        assert created.content == "hello"
        assert created.state == "proposed"
        assert created.confidence_score == 5.0

    def test_get_missing(self, repo):
        assert repo.get("nonexistent") is None

    def test_get_created(self, repo, make_candidate):
        cm = make_candidate()
        fetched = repo.get(cm.id)
        assert fetched is not None
        assert fetched.id == cm.id
        assert fetched.content == "test content"

    def test_list_empty(self, repo):
        assert repo.list() == []

    def test_list_filters_by_state(self, repo, make_candidate):
        a = make_candidate(state="proposed")
        make_candidate(state="supported")
        assert len(repo.list(state="proposed")) == 1
        assert repo.list(state="proposed")[0].id == a.id

    def test_search_returns_matching(self, repo, make_candidate):
        cm = make_candidate()
        results = repo.search("test")
        assert len(results) == 1
        assert results[0].id == cm.id

    def test_search_no_match(self, repo, make_candidate):
        make_candidate()
        assert repo.search("zzz_nonexistent") == []


# ── promote: valid transitions ────────────────────────────────────────────────


class TestPromoteProposedToSupported:
    def test_transition(self, repo, make_candidate):
        cm = make_candidate(state="proposed")
        updated = repo.promote(cm.id, "supported", "user_1", "good evidence")
        assert updated is not None
        assert updated.state == "supported"

    def test_audit_trail_recorded(self, repo, make_candidate):
        cm = make_candidate(state="proposed")
        updated = repo.promote(cm.id, "supported", "reviewer_42", "looks solid")
        trail = updated.audit_trail
        assert len(trail) == 1
        entry = trail[0]
        assert entry["action"] == "promote"
        assert entry["to_state"] == "supported"
        assert entry["reviewer_id"] == "reviewer_42"
        assert entry["note"] == "looks solid"
        assert "timestamp" in entry

    def test_updated_at_advances(self, repo, make_candidate):
        cm = make_candidate(state="proposed")
        before = cm.updated_at
        time.sleep(0.01)
        updated = repo.promote(cm.id, "supported", "r1", "")
        assert updated.updated_at > before


class TestPromoteSupportedToVerified:
    def test_transition(self, repo, make_candidate):
        cm = make_candidate(state="supported")
        updated = repo.promote(cm.id, "verified", "admin", "strong consensus")
        assert updated is not None
        assert updated.state == "verified"

    def test_audit_trail_accumulates(self, repo, make_candidate):
        cm = make_candidate(state="proposed")
        repo.promote(cm.id, "supported", "r1", "step1")
        updated = repo.promote(cm.id, "verified", "r2", "step2")
        assert len(updated.audit_trail) == 2
        assert updated.audit_trail[1]["to_state"] == "verified"


class TestPromoteToRejected:
    @pytest.mark.parametrize("initial_state", ["proposed", "supported", "verified"])
    def test_reject_from_any_state(self, repo, make_candidate, initial_state):
        cm = make_candidate(state=initial_state)
        updated = repo.promote(cm.id, "rejected", "moderator", "incorrect")
        assert updated is not None
        assert updated.state == "rejected"

    def test_rejected_cannot_promote_forward(self, repo, make_candidate):
        cm = make_candidate(state="rejected")
        with pytest.raises(ValueError):
            repo.promote(cm.id, "proposed", None, None)


# ── invalid transitions ──────────────────────────────────────────────────────


class TestInvalidTransitions:
    def test_verified_to_proposed_raises(self, repo, make_candidate):
        cm = make_candidate(state="verified")
        with pytest.raises(ValueError, match="Invalid transition"):
            repo.promote(cm.id, "proposed", None, None)

    def test_supported_to_proposed_raises(self, repo, make_candidate):
        cm = make_candidate(state="supported")
        with pytest.raises(ValueError, match="Invalid transition"):
            repo.promote(cm.id, "proposed", None, None)

    def test_state_unchanged_after_invalid(self, repo, make_candidate):
        cm = make_candidate(state="verified")
        original_updated = cm.updated_at
        with pytest.raises(ValueError):
            repo.promote(cm.id, "proposed", None, None)
        still = repo.get(cm.id)
        assert still.state == "verified"
        assert still.updated_at == original_updated

    def test_nonexistent_id_returns_none(self, repo):
        assert repo.promote("missing_id", "supported", None, None) is None


# ── update_score ──────────────────────────────────────────────────────────────


class TestUpdateScore:
    def test_increases_score(self, repo, make_candidate):
        cm = make_candidate(score=5.0)
        repo.update_score(cm.id, 12.0)
        fetched = repo.get(cm.id)
        assert fetched.confidence_score == 12.0

    def test_decreases_score(self, repo, make_candidate):
        cm = make_candidate(score=15.0)
        repo.update_score(cm.id, 3.0)
        fetched = repo.get(cm.id)
        assert fetched.confidence_score == 3.0

    def test_timestamp_advances(self, repo, make_candidate):
        cm = make_candidate()
        before = cm.updated_at
        time.sleep(0.01)
        repo.update_score(cm.id, 10.0)
        fetched = repo.get(cm.id)
        assert fetched.updated_at > before

    def test_missing_id_no_error(self, repo):
        # update_score does not validate existence; SQLite just affects 0 rows
        repo.update_score("no_such_id", 99.0)


# ── end-to-end scoring through service ────────────────────────────────────────


class TestScoreIntegration:
    def test_score_then_promote_chain(self, temp_workspace):
        from geomemory.services.candidate_memory_service import CandidateMemoryService

        svc = CandidateMemoryService(temp_workspace.conn)
        cm = svc.create("ndvi is useful", memory_type="fact")
        assert cm.state == "proposed"

        # Add confirmations to push into supported
        svc.score(cm.id, {"confirming": 3})
        refreshed = svc.get(cm.id)
        assert refreshed.state == "supported"

        # Add more to push into verified (5 confirm cap at +6 → score 11, still supported;
        # adding multiple_actors adds +3 for 14 → verified)
        svc.score(cm.id, {"confirming": 5, "multiple_actors": True})
        refreshed = svc.get(cm.id)
        assert refreshed.state == "verified"
