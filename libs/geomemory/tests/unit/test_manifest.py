"""Unit tests for the index manifest."""

from __future__ import annotations

from geomemory.index.manifest import (
    create_manifest,
    load_manifest,
    manifest_exists,
    write_manifest,
)


class TestManifest:
    def test_create_defaults(self):
        m = create_manifest(space_id="text.nomic.v1", model_id="nomic", dimension=768)
        assert m.normalization == "l2"
        assert m.chunker == "header_then_token"
        assert m.chunk_size == 1000
        assert m.chunk_overlap == 150
        assert m.doc_count == 0

    def test_write_load_roundtrip(self, tmp_path):
        m = create_manifest(
            space_id="text.nomic.v1",
            model_id="nomic-embed-text-v2-moe",
            dimension=768,
            doc_count=42,
        )
        write_manifest(tmp_path, m)
        assert manifest_exists(tmp_path)
        loaded = load_manifest(tmp_path)
        assert loaded.space_id == m.space_id
        assert loaded.model_id == m.model_id
        assert loaded.dimension == 768
        assert loaded.doc_count == 42

    def test_manifest_not_exists(self, tmp_path):
        assert not manifest_exists(tmp_path)
