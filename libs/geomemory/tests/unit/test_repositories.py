"""Tests for the storage repositories."""

from __future__ import annotations

import hashlib

from geomemory.core.models import Asset, AssetRevision, Segment
from geomemory.storage.repositories.asset_repo import AssetRepository, AssetRevisionRepository
from geomemory.storage.repositories.segment_repo import SegmentRepository


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _col(ws) -> str:
    return ws.create_collection("docs").id


class TestAssetRepository:
    def test_insert_and_get(self, temp_workspace):
        repo = AssetRepository(temp_workspace.conn)
        asset = Asset(collection_id=_col(temp_workspace), kind="document", title="doc.md")
        repo.insert(asset)
        assert repo.get(asset.id).id == asset.id
        assert repo.count() == 1

    def test_get_by_collection(self, temp_workspace):
        repo = AssetRepository(temp_workspace.conn)
        c1, c2 = _col(temp_workspace), _col(temp_workspace)
        a1 = Asset(collection_id=c1, kind="document")
        a2 = Asset(collection_id=c2, kind="code")
        repo.insert(a1)
        repo.insert(a2)
        assert [a.id for a in repo.get_by_collection(c1)] == [a1.id]

    def test_soft_delete(self, temp_workspace):
        repo = AssetRepository(temp_workspace.conn)
        asset = Asset(collection_id=_col(temp_workspace), kind="document")
        repo.insert(asset)
        assert repo.soft_delete(asset.id) is True
        assert repo.get_by_collection(asset.collection_id) == []
        assert repo.soft_delete(asset.id) is False


class TestAssetRevisionRepository:
    def _make_asset(self, ws) -> str:
        repo = AssetRepository(ws.conn)
        asset = Asset(collection_id=_col(ws), kind="document")
        repo.insert(asset)
        return asset.id

    def test_roundtrip_with_json_metadata(self, temp_workspace):
        repo = AssetRevisionRepository(temp_workspace.conn)
        rev = AssetRevision(
            asset_id=self._make_asset(temp_workspace), hash=_sha("content"), mime_type="text/markdown",
            metadata={"parser": "v1"},
        )
        repo.insert(rev)
        loaded = repo.get(rev.id)
        assert loaded.metadata == {"parser": "v1"}

    def test_get_by_hash(self, temp_workspace):
        repo = AssetRevisionRepository(temp_workspace.conn)
        rev = AssetRevision(asset_id=self._make_asset(temp_workspace), hash=_sha("x"), mime_type="text/plain")
        repo.insert(rev)
        assert repo.get_by_hash(_sha("x")).id == rev.id
        assert repo.get_by_hash(_sha("other")) is None


class TestSegmentRepository:
    def _make_revision(self, ws) -> str:
        ar = AssetRepository(ws.conn)
        asset = Asset(collection_id=_col(ws), kind="document")
        ar.insert(asset)
        rev = AssetRevision(asset_id=asset.id, hash=_sha("x"), mime_type="text/plain")
        AssetRevisionRepository(ws.conn).insert(rev)
        return rev.id

    def test_insert_and_fts_search(self, temp_workspace):
        repo = SegmentRepository(temp_workspace.conn)
        seg = Segment(revision_id=self._make_revision(temp_workspace), text="NDVI vegetation health index")
        repo.insert(seg)
        hits = repo.fts_search("vegetation", top_k=5)
        assert any(h.id == seg.id for h in hits)

    def test_get_by_revision(self, temp_workspace):
        repo = SegmentRepository(temp_workspace.conn)
        r1, r2 = self._make_revision(temp_workspace), self._make_revision(temp_workspace)
        s1 = Segment(revision_id=r1, text="a")
        s2 = Segment(revision_id=r2, text="b")
        repo.insert(s1)
        repo.insert(s2)
        assert [s.id for s in repo.get_by_revision(r1)] == [s1.id]
        assert repo.count_by_revision(r1) == 1