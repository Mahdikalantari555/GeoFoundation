"""Tests for dashboard-facing public API helpers and doctor service."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_stats_empty_workspace(temp_workspace) -> None:
    stats = temp_workspace.stats()
    assert stats["collections"] == 0
    assert stats["assets"] == 0
    assert stats["segments"] == 0
    assert stats["spatial_entities"] == 0
    assert stats["feedback_events"] == 0
    assert isinstance(stats["storage_bytes"], int)


@pytest.mark.unit
def test_stats_after_ingest(temp_workspace, sample_markdown) -> None:
    ws = temp_workspace
    col = ws.create_collection("papers")
    ws.ingest(str(sample_markdown), collection_id=col.id)
    stats = ws.stats()
    assert stats["collections"] == 1
    assert stats["assets"] == 1
    assert stats["segments"] >= 1


@pytest.mark.unit
def test_review_example_accept_reject(temp_workspace) -> None:
    ws = temp_workspace
    from geomemory.core.models import DatasetExample, FeedbackEvent

    ev = ws.record_feedback(
        FeedbackEvent(
            target_type="answer",
            target_id="ans1",
            label="answer_rating",
            payload={"rating": 1},
        )
    )
    from geomemory.storage.repositories.feedback_repo import DatasetExampleRepository

    dsx = DatasetExampleRepository(ws.conn).create(
        DatasetExample(task_type="rag_eval", source_feedback_ids=[ev.id])
    )
    assert len(ws.get_review_queue()) == 1
    assert ws.review_example(dsx.id, accept=True)
    assert len(ws.get_review_queue()) == 0
    # Accepting an already-reviewed example returns False (no change).
    assert not ws.review_example(dsx.id, accept=True)


@pytest.mark.unit
def test_update_settings_validated(temp_workspace) -> None:
    ws = temp_workspace
    updated = ws.update_settings(batch_size=32, model_path="/models/qwen.gguf")
    assert updated.batch_size == 32
    assert updated.model_path == "/models/qwen.gguf"
    assert ws.settings.batch_size == 32
    with pytest.raises(ValueError):
        ws.update_settings(not_a_real_field=1)


@pytest.mark.unit
def test_doctor_environment():
    from geomemory.services.doctor import doctor_environment

    env = doctor_environment()
    assert env["python_ok"] is True
    assert env["core_ok"] is True
    assert isinstance(env["optional_deps"], dict)
    assert "rasterio" in env["optional_deps"]


@pytest.mark.unit
def test_doctor_workspace_ok(temp_workspace):
    from geomemory.services.doctor import doctor_workspace, doctor_workspace_open

    rep = doctor_workspace(temp_workspace.path)
    assert rep["ok"] is True
    assert rep["checks"]["marker_exists"] is True
    assert rep["checks"]["settings_valid"] is True

    opened = doctor_workspace_open(temp_workspace.path)
    assert opened["ok"] is True
    assert opened["checks"]["stats"] is True


@pytest.mark.unit
def test_doctor_workspace_missing(tmp_path):
    from geomemory.services.doctor import doctor_workspace

    rep = doctor_workspace(tmp_path / "nope")
    assert rep["ok"] is False
