"""Tests for the persisted index service and offline embedder."""

from __future__ import annotations

import numpy as np
import pytest

from geomemory.core.models import IndexRecord, SearchRequest
from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.index.manifest import load_manifest, manifest_exists
from geomemory.index.vector_backend import VectorBackend
from geomemory.services.index_service import IndexService
from geomemory.storage.repositories.embedding_repo import EmbeddingRepository


class TestHashingTextEmbedder:
    def test_space_id_and_model_id(self):
        embedder = HashingTextEmbedder()
        assert embedder.space_id == "text.hash.v1"
        assert embedder.model_id == "hashing-ngram-v1"

    def test_embed_shape_and_unit_norm(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed(["NDVI vegetation health", "flood mapping"])
        assert vectors.shape == (2, 256)
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)

    def test_deterministic(self):
        embedder = HashingTextEmbedder()
        a = embedder.embed(["crop stress detection"])
        b = embedder.embed(["crop stress detection"])
        assert np.allclose(a, b)

    def test_similar_texts_are_closer(self):
        embedder = HashingTextEmbedder()
        base = embedder.embed(["NDVI measures vegetation health"])
        similar = embedder.embed(["NDVI measures vegetation health"])
        unrelated = embedder.embed(["flood mapping with SAR"])
        sim = float(np.dot(base[0], similar[0]))
        unrel = float(np.dot(base[0], unrelated[0]))
        assert sim > unrel

    def test_embed_batch(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed_batch(["a", "b", "c"], batch_size=2)
        assert vectors.shape == (3, 256)


class TestVectorBackend:
    def test_upsert_and_count(self):
        backend = VectorBackend(space_id="text.hash.v1")
        backend.upsert(
            [IndexRecord(id="s1", text="NDVI vegetation health")],
            embeddings=np.array([[1.0, 0.0, 0.0]], dtype=np.float32),
        )
        assert backend.count() == 1

    def test_search_ranks_by_cosine(self):
        backend = VectorBackend(space_id="text.hash.v1")
        backend.upsert(
            [
                IndexRecord(id="s1", text="NDVI vegetation health"),
                IndexRecord(id="s2", text="Flood mapping with SAR"),
            ],
            embeddings=np.array(
                [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
            ),
        )
        request = SearchRequest(
            query="vegetation",
            query_embedding=np.array([1.0, 0.0, 0.0], dtype=np.float32),
            mode="dense",
            top_k=2,
            top_n=2,
        )
        hits = backend.search(request)
        assert hits[0].id == "s1"
        assert hits[0].dense_score > 0.9

    def test_search_without_query_embedding_returns_empty(self):
        backend = VectorBackend(space_id="text.hash.v1")
        backend.upsert(
            [IndexRecord(id="s1", text="text")],
            embeddings=np.array([[1.0, 0.0]], dtype=np.float32),
        )
        assert backend.search(SearchRequest(query="x", mode="dense")) == []

    def test_delete(self):
        backend = VectorBackend(space_id="text.hash.v1")
        backend.upsert(
            [IndexRecord(id="s1", text="a"), IndexRecord(id="s2", text="b")],
            embeddings=np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        )
        backend.delete(["s1"])
        assert backend.count() == 1
        assert backend.records()[0].id == "s2"

    def test_save_and_load_roundtrip(self, tmp_path):
        backend = VectorBackend(space_id="text.hash.v1")
        backend.upsert(
            [IndexRecord(id="s1", text="NDVI", metadata={"locator": {"file": "x.md"}})],
            embeddings=np.array([[1.0, 0.0, 0.0]], dtype=np.float32),
        )
        backend.save(tmp_path / "idx")
        loaded = VectorBackend.load(tmp_path / "idx", space_id="text.hash.v1")
        assert loaded.count() == 1
        assert loaded.records()[0].id == "s1"
        assert loaded.records()[0].metadata["locator"] == {"file": "x.md"}
        assert VectorBackend.exists(tmp_path / "idx")

    def test_load_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            VectorBackend.load(tmp_path / "nope")


class TestIndexService:
    def test_build_persists_embeddings_and_manifest(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        service = IndexService(ws.conn, ws.index_dir)
        summary = service.build("text.hash.v1")

        assert summary["embedded"] > 0
        assert summary["indexed"] == summary["embedded"]
        assert summary["model_id"] == "hashing-ngram-v1"

        # Embedding records persisted in SQLite.
        repo = EmbeddingRepository(ws.conn)
        records = repo.get_by_space("text.hash.v1")
        assert len(records) == summary["embedded"]
        assert all(r.space_id == "text.hash.v1" for r in records)
        assert all(r.target_type == "segment" for r in records)

        # Manifest + backend persisted on disk.
        backend_dir = ws.index_dir / "text.hash.v1"
        assert manifest_exists(backend_dir)
        manifest = load_manifest(backend_dir)
        assert manifest.space_id == "text.hash.v1"
        assert manifest.model_id == "hashing-ngram-v1"
        assert manifest.doc_count == summary["indexed"]
        assert VectorBackend.exists(backend_dir)

    def test_build_is_incremental(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        service = IndexService(ws.conn, ws.index_dir)
        first = service.build("text.hash.v1")
        second = service.build("text.hash.v1")
        assert second["embedded"] == 0
        assert second["indexed"] == first["indexed"]

    def test_rebuild_forces_reembed(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        service = IndexService(ws.conn, ws.index_dir)
        service.build("text.hash.v1")
        rebuilt = service.rebuild("text.hash.v1")
        assert rebuilt["embedded"] > 0
        assert rebuilt["indexed"] == rebuilt["embedded"]

    def test_search_returns_hits_after_build(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        service = IndexService(ws.conn, ws.index_dir)
        service.build("text.hash.v1")
        hits = service.search("NDVI", space_id="text.hash.v1")
        assert hits, "expected dense hits after build"
        assert hits[0].dense_score > 0.0

    def test_search_without_index_returns_empty(self, temp_workspace):
        service = IndexService(temp_workspace.conn, temp_workspace.index_dir)
        assert service.search("anything", space_id="text.hash.v1") == []


class TestWorkspaceIndexWiring:
    def test_build_index_then_dense_search(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        ws.build_index("text.hash.v1")
        result = ws.search("NDVI crop stress", mode="dense")
        assert result.total_hits > 0

    def test_rebuild_index(self, temp_workspace, sample_markdown):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)
        ws.build_index("text.hash.v1")
        ws.rebuild_index("text.hash.v1")
        assert (ws.index_dir / "text.hash.v1" / "manifest.json").is_file()
