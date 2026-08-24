"""Unit tests for the chunkers."""

from __future__ import annotations

from geomemory.core.models import ParsedObject, SourceRef
from geomemory.ingest.chunkers import FixedSizeChunker, HeaderThenTokenChunker


def _doc(text: str) -> ParsedObject:
    return ParsedObject(
        source=SourceRef(path="test.md"),
        mime_type="text/markdown",
        title="test",
        text=text,
    )


class TestHeaderThenTokenChunker:
    def test_respects_headers(self):
        text = "# Intro\n\nFirst paragraph.\n\n## Methods\n\nSecond paragraph.\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert len(drafts) >= 2
        # First chunk is the heading section.
        assert drafts[0].segment_type == "heading"
        assert "Intro" in drafts[0].text

    def test_parent_section_id(self):
        text = "# A\n\nbody a\n\n# B\n\nbody b\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert drafts[0].parent_section_id is not None
        assert drafts[1].parent_section_id is not None

    def test_neighbor_ids(self):
        text = "# A\n\nbody a\n\n# B\n\nbody b\n"
        drafts = list(HeaderThenTokenChunker().split(_doc(text)))
        assert len(drafts) >= 2
        assert drafts[0].neighbor_ids == ["next:1"]
        assert drafts[1].neighbor_ids == ["prev:0"]

    def test_long_section_split(self):
        # A single section with many tokens should be split.
        text = "# Long\n\n" + "word " * 2000
        drafts = list(HeaderThenTokenChunker(chunk_size=100, chunk_overlap=20).split(_doc(text)))
        assert len(drafts) > 1
        # Overlap means consecutive chunks share tokens.
        assert drafts[0].locator.get("token_span") is not None

    def test_empty_document(self):
        drafts = list(HeaderThenTokenChunker().split(_doc("")))
        assert drafts == []


class TestFixedSizeChunker:
    def test_splits_by_token_count(self):
        text = " ".join(f"token{i}" for i in range(100))
        drafts = list(FixedSizeChunker(chunk_size=30, chunk_overlap=5).split(_doc(text)))
        assert len(drafts) > 1
        assert all(d.segment_type == "paragraph" for d in drafts)

    def test_small_document_single_chunk(self):
        drafts = list(FixedSizeChunker().split(_doc("short text")))
        assert len(drafts) == 1

    def test_empty(self):
        assert list(FixedSizeChunker().split(_doc(""))) == []

    def test_neighbors(self):
        text = " ".join(f"token{i}" for i in range(100))
        drafts = list(FixedSizeChunker(chunk_size=30, chunk_overlap=5).split(_doc(text)))
        assert drafts[0].neighbor_ids == ["next:1"]