"""Tests for ingestion pipeline, chunkers, loaders, and dirty-data robustness."""
from __future__ import annotations

from pathlib import Path

import json as _json

import numpy as np
import pytest

from geomemory.core.models import ParsedObject, SearchHit, SourceRef
from geomemory.embeddings.normalization import l2_normalize
from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.ingest.chunkers import FixedSizeChunker, HeaderThenTokenChunker
from geomemory.ingest.loaders import CodeLoader, NotebookLoader, PdfLoader, TextLoader, get_loader
from geomemory.services.ingestion_service import IngestionService
from geomemory.storage.repositories.segment_repo import SegmentRepository
from geomemory.storage.object_store import ObjectStore


# ===========================================================================
# Chunker dirty inputs
# ===========================================================================

def _doc(text: str) -> ParsedObject:
    return ParsedObject(
        source=SourceRef(path="test.md"),
        mime_type="text/markdown",
        title="test",
        text=text,
    )


class TestChunkerDirtyInputs:
    def test_header_chunker_empty_document(self):
        assert list(HeaderThenTokenChunker().split(_doc(""))) == []

    def test_header_chunker_whitespace_only(self):
        result = list(HeaderThenTokenChunker().split(_doc("   \n\n  \t\n")))
        assert result == [] or all((not c.text.strip()) for c in result)

    def test_header_chunker_single_heading_only(self):
        result = list(HeaderThenTokenChunker().split(_doc("# Just a title\n")))
        assert len(result) >= 1

    def test_header_chunker_unicode_content(self):
        text = "# title\n\nسلام دوست عزیز\n"
        result = list(HeaderThenTokenChunker().split(_doc(text)))
        assert any("سلام" in c.text for c in result)

    def test_header_chunker_deeply_nested_headers(self):
        text = "# A\n## B\n### C\n#### D\nbody\n"
        result = list(HeaderThenTokenChunker().split(_doc(text)))
        assert len(result) >= 2

    def test_fixed_size_empty_document(self):
        assert list(FixedSizeChunker().split(_doc(""))) == []

    def test_fixed_size_single_char(self):
        result = list(FixedSizeChunker(chunk_size=1, chunk_overlap=0).split(_doc("x")))
        assert len(result) == 1
        assert result[0].text == "x"

    def test_fixed_size_large_overlap(self):
        text = " ".join(f"w{i}" for i in range(10))
        chunks = list(FixedSizeChunker(chunk_size=100, chunk_overlap=50).split(_doc(text)))
        assert len(chunks) == 1

    def test_fixed_size_overlap_exceeds_chunk_size(self):
        """When overlap >= chunk_size, step becomes 1 so chunking still works."""
        text = " ".join(f"w{i}" for i in range(10))
        chunks = list(FixedSizeChunker(chunk_size=5, chunk_overlap=10).split(_doc(text)))
        assert len(chunks) >= 1

    def test_fixed_size_zero_chunk_size(self):
        """chunk_size=0 with non-empty text produces empty drafts."""
        text = "hello world"
        chunks = list(FixedSizeChunker(chunk_size=0, chunk_overlap=0).split(_doc(text)))
        assert all(chunk.text == "" for chunk in chunks)

    def test_header_chunker_neighbors_on_multi_chunk(self):
        text = "# H1\n\n" + "word " * 500
        chunks = list(HeaderThenTokenChunker(chunk_size=20, chunk_overlap=5).split(_doc(text)))
        assert len(chunks) > 1
        assert chunks[0].neighbor_ids == ["next:1"]
        assert chunks[-1].neighbor_ids == [f"prev:{len(chunks) - 2}"]

    def test_header_chunker_preserves_parent_section(self):
        text = "# Main\n\npara\n## Sub\n\npara2\n"
        chunks = list(HeaderThenTokenChunker().split(_doc(text)))
        assert all(c.parent_section_id is not None for c in chunks)

    def test_fixed_size_chunk_metadata_locator(self):
        text = " ".join(f"token{i}" for i in range(100))
        chunks = list(FixedSizeChunker(chunk_size=20, chunk_overlap=5).split(_doc(text)))
        assert any(c.locator.get("token_span") for c in chunks)


# ===========================================================================
# Loader dirty inputs
# ===========================================================================

class TestLoaderDirtyInputs:
    def test_text_loader_empty_file(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("", encoding="utf-8")
        loader = TextLoader()
        objs = list(loader.load(SourceRef(path=str(p))))
        assert objs == [] or all((not o.text.strip()) for o in objs)

    def test_text_loader_unicode_markdown(self, tmp_path):
        p = tmp_path / "uni.md"
        p.write_text("# تحلیل NDVI\n\nمتن فارسی", encoding="utf-8")
        objs = list(TextLoader().load(SourceRef(path=str(p))))
        assert any(("NDVI" in o.text or "تحلیل" in o.text) for o in objs)

    def test_code_loader_empty_python_file(self, tmp_path):
        p = tmp_path / "empty.py"
        p.write_text("", encoding="utf-8")
        objs = list(CodeLoader().load(SourceRef(path=str(p))))
        assert objs == [] or all((not o.text.strip()) for o in objs)

    def test_code_loader_syntax_error_fallback(self, tmp_path):
        p = tmp_path / "bad.py"
        p.write_text("def broken(:\n    pass\n", encoding="utf-8")
        loader = CodeLoader()
        objs = list(loader.load(SourceRef(path=str(p))))
        assert len(objs) >= 1

    def test_notebook_loader_empty_cells(self, tmp_path):
        nb = {
            "cells": [],
            "metadata": {"language_info": {"name": "python"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        p = tmp_path / "empty.ipynb"
        p.write_text(_json.dumps(nb), encoding="utf-8")
        objs = list(NotebookLoader().load(SourceRef(path=str(p))))
        assert len(objs) == 1
        assert objs[0].metadata["cell_count"] == 0

    def test_pdf_loader_without_pymupdf_fallback(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4 fake content body")
        objs = list(PdfLoader().load(SourceRef(path=str(p))))
        assert len(objs) >= 1
        if objs[0].metadata.get("fallback"):
            assert objs[0].text

    def test_get_loader_unknown_returns_none(self, tmp_path):
        p = tmp_path / "file.xyz"
        p.write_text("x")
        assert get_loader(SourceRef(path=str(p))) is None

    def test_text_loader_markdown_with_frontmatter(self, tmp_path):
        content = "---\ntitle: RS Notes\n---\n# NDVI Analysis\nbody\n"
        p = tmp_path / "fm.md"
        p.write_text(content, encoding="utf-8")
        objs = list(TextLoader().load(SourceRef(path=str(p))))
        assert len(objs) >= 1
        assert "NDVI" in objs[0].text

    def test_code_loader_docstring_extraction(self, tmp_path):
        code = 'def compute_ndvi(nir, red):\n    """Compute NDVI index."""\n    return (nir - red) / (nir + red)\n'
        p = tmp_path / "ndvi.py"
        p.write_text(code, encoding="utf-8")
        objs = list(CodeLoader().load(SourceRef(path=str(p))))
        assert len(objs) == 1
        units = objs[0].metadata.get("code_units", [])
        names = {u["name"] for u in units}
        assert "compute_ndvi" in names


# ===========================================================================
# Embedding robustness: dirty vectors, empty inputs
# ===========================================================================

class TestEmbeddingRobustness:
    def test_hashing_embedder_empty_input(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed([])
        assert vectors.shape[0] == 0

    def test_hashing_embedder_single_token(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed(["NDVI"])
        assert vectors.shape[1] == 256

    def test_hashing_embedder_unit_norm(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed(["Sentinel-2 multispectral"])
        norms = np.linalg.norm(vectors, axis=1)
        assert np.allclose(norms, 1.0)

    def test_hashing_embedder_unicode(self):
        embedder = HashingTextEmbedder()
        vectors = embedder.embed(["تحلیل داده‌های ماهواره‌ای"])
        assert vectors.shape[0] == 1
        assert not np.isnan(vectors).any()

    def test_hashing_embedder_deterministic(self):
        embedder = HashingTextEmbedder()
        v1 = embedder.embed(["crop stress"])
        v2 = embedder.embed(["crop stress"])
        assert np.allclose(v1, v2)

    def test_hashing_embedder_different_inputs_differ(self):
        embedder = HashingTextEmbedder()
        v1 = embedder.embed(["NDVI"])
        v2 = embedder.embed(["SAR flood mapping"])
        assert not np.allclose(v1, v2)

    def test_hashing_embedder_long_text(self):
        embedder = HashingTextEmbedder()
        long_text = " ".join([f"token{i}" for i in range(1000)])
        vectors = embedder.embed([long_text])
        assert vectors.shape == (1, 256)
        assert not np.isnan(vectors).any()

    def test_l2_normalize_zero_vector(self):
        v = l2_normalize(np.zeros((1, 256), dtype=np.float32))
        assert np.allclose(v, 0.0)

    def test_l2_normalize_already_normalized(self):
        v = np.eye(256, dtype=np.float32)
        out = l2_normalize(v)
        assert np.allclose(out, v)
