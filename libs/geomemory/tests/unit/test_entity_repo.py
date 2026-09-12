"""Unit tests for EntityRepository."""

from __future__ import annotations

from geomemory.core.models import Entity
from geomemory.storage.repositories.entity_repo import EntityRepository


def _make_entity(repo: EntityRepository, name: str, kind: str, workspace_id: str) -> Entity:
    return repo.upsert_name_match(name, kind, workspace_id)


class TestEntityRepository:
    def test_create_and_get(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        entity = Entity(name="NDVI", kind="metric", workspace_id=ws_id, evidence_id="seg_abc")
        repo.create(entity)
        loaded = repo.get(entity.id)
        assert loaded is not None
        assert loaded.name == "NDVI"
        assert loaded.kind == "metric"
        assert loaded.evidence_id == "seg_abc"

    def test_upsert_name_match_dedup(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        e1 = repo.upsert_name_match("NDVI", "metric", ws_id)
        e2 = repo.upsert_name_match("NDVI", "metric", ws_id)
        assert e1.id == e2.id
        assert repo.count() == 1

    def test_list_by_kind(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        repo.upsert_name_match("NDVI", "metric", ws_id)
        repo.upsert_name_match("EVI", "metric", ws_id)
        repo.upsert_name_match("soil", "concept", ws_id)
        metrics = repo.list_by_kind("metric", workspace_id=ws_id)
        assert len(metrics) == 2
        names = {m.name for m in metrics}
        assert names == {"NDVI", "EVI"}

    def test_list_by_workspace(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        repo.upsert_name_match("Khuzestan", "location", ws_id)
        repo.upsert_name_match("Sentinel-2", "sensor", ws_id)
        ents = repo.list_by_workspace(ws_id)
        assert len(ents) == 2

    def test_get_by_evidence(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        entity = Entity(name="salinity", kind="stress_type", workspace_id=ws_id, evidence_id="seg_xyz")
        repo.create(entity)
        hits = repo.get_by_evidence("seg_xyz")
        assert len(hits) == 1
        assert hits[0].name == "salinity"

    def test_spatial_bbox_serialization(self, temp_workspace):
        ws_id = temp_workspace._workspace_id()
        repo = EntityRepository(temp_workspace.conn)
        entity = Entity(name="Khuzestan", kind="location", workspace_id=ws_id, spatial_bbox=(51.0, 32.0, 52.0, 33.0))
        repo.create(entity)
        loaded = repo.get(entity.id)
        assert loaded.spatial_bbox == (51.0, 32.0, 52.0, 33.0)
