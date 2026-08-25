"""Integration tests for the hybrid search pipeline."""
from __future__ import annotations

import hashlib

import pytest

from geomemory.core.models import (
    Collection,
    SearchFilters,
    SearchHit,
    SearchResult,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.retrieval.query_parser import QueryParser
from geomemory.retrieval.search_service import SearchService
from geomemory.storage.database import connect, initialize


@pytest.fixture
def search_db(tmp_path):
    db = tmp_path / "search.db"
    conn = connect(db)
    initialize(conn)
    return conn


@pytest.fixture
def populated_search_db(search_db):
    """DB with a workspace, collection, asset, revision, and segments ready for search."""
    ws_id = "ws_search"
    search_db.execute("INSERT INTO workspace (id, name) VALUES (?, ?)", (ws_id, "search-ws"))
    col = Collection(workspace_id=ws_id, name="docs")
    search_db.execute(
        "INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)",
        (col.id, col.workspace_id, col.name),
    )

    asset = type("Asset", (), {"id": "asset1", "collection_id": col.id, "kind": "document"})()
    search_db.execute(
        "INSERT INTO asset (id, collection_id, kind) VALUES (?, ?, ?)",
        (asset.id, asset.collection_id, asset.kind),
    )

    rev_id = "rev1"
    rev_hash = hashlib.sha256(b"test content").hexdigest()
    search_db.execute(
        "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (rev_id, asset.id, rev_hash, "text/markdown", 12, "0.1.0"),
    )

    segments = [
        ("seg1", "NDVI vegetation health index for crop monitoring"),
        ("seg2", "Sentinel-2 multispectral imagery classification"),
        ("seg3", "SAR flood mapping with Sentinel-1 radar data"),
        ("seg4", "Landsat-8 thermal band analysis for urban heat"),
        ("seg5", "Machine learning approaches to remote sensing"),
    ]
    for seg_id, text in segments:
        search_db.execute(
            "INSERT INTO segment (id, revision_id, text, segment_type) VALUES (?, ?, ?, ?)",
            (seg_id, rev_id, text, "paragraph"),
        )
    search_db.commit()
    return search_db


class TestSearchServiceIntegration:
    def test_search_returns_results(self, populated_search_db):
        svc = SearchService(
            backends=[_FakeSparseBackend(populated_search_db), _FakeDenseBackend([])],
            parser=QueryParser(),
        )
        result = svc.search("NDVI")
        assert result.total_hits > 0

    def test_search_with_spatial_filter(self, populated_search_db):
        svc = SearchService(
            backends=[_FakeSparseBackend(populated_search_db), _FakeDenseBackend([])],
            parser=QueryParser(),
        )
        filt = SpatialFilter(bbox=(0, 0, 180, 90))
        result = svc.search("Sentinel", filters=SearchFilters(spatial=filt))
        assert isinstance(result, SearchResult)

    def test_search_with_temporal_filter(self, populated_search_db):
        svc = SearchService(
            backends=[_FakeSparseBackend(populated_search_db), _FakeDenseBackend([])],
            parser=QueryParser(),
        )
        filt = TemporalFilter(from_="2020-01-01", to="2030-12-31", field="acquired_at")
        result = svc.search("NDVI", filters=SearchFilters(temporal=filt))
        assert isinstance(result, SearchResult)

    def test_search_empty_query_no_crash(self, populated_search_db):
        svc = SearchService(
            backends=[_FakeSparseBackend(populated_search_db), _FakeDenseBackend([])],
            parser=QueryParser(),
        )
        result = svc.search("")
        assert isinstance(result, SearchResult)


class _FakeSparseBackend:
    def __init__(self, conn):
        self._conn = conn

    def search(self, request):
        query = getattr(request, "query", "") or ""
        rows = self._conn.execute(
            "SELECT id, text, segment_type FROM segment WHERE text LIKE ? LIMIT 10",
            (f"%{query}%",),
        ).fetchall()
        return [
            SearchHit(id=r[0], score=1.0, metadata={"text": r[1], "segment_type": r[2]})
            for r in rows
        ]


class _FakeDenseBackend:
    def __init__(self, hits):
        self._hits = hits

    def search(self, request):
        return list(self._hits)
