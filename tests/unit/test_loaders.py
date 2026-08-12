"""Unit tests for the ingest loaders."""

from __future__ import annotations

from geomemory.core.models import SourceRef
from geomemory.ingest.loaders import (
    CodeLoader,
    NotebookLoader,
    PdfLoader,
    TextLoader,
    get_loader,
)


class TestTextLoader:
    def test_supports_markdown(self, sample_markdown):
        loader = TextLoader()
        assert loader.supports(SourceRef(path=str(sample_markdown)))

    def test_load(self, sample_markdown):
        loader = TextLoader()
        objs = list(loader.load(SourceRef(path=str(sample_markdown))))
        assert len(objs) == 1
        assert "NDVI" in objs[0].text
        assert objs[0].mime_type == "text/markdown"


class TestCodeLoader:
    def test_supports_python(self, sample_python):
        loader = CodeLoader()
        assert loader.supports(SourceRef(path=str(sample_python)))

    def test_load_python_ast(self, sample_python):
        loader = CodeLoader()
        objs = list(loader.load(SourceRef(path=str(sample_python))))
        assert len(objs) == 1
        units = objs[0].metadata["code_units"]
        names = {u["name"] for u in units}
        assert "compute_ndvi" in names
        assert "VegetationIndex" in names
        # Function has a signature and docstring.
        fn = next(u for u in units if u["name"] == "compute_ndvi")
        assert fn["signature"].startswith("compute_ndvi(")
        assert "NDVI" in fn["docstring"]
        assert fn["start_line"] >= 1


class TestNotebookLoader:
    def test_load(self, sample_notebook):
        loader = NotebookLoader()
        objs = list(loader.load(SourceRef(path=str(sample_notebook))))
        assert len(objs) == 1
        assert objs[0].metadata["cell_count"] == 2
        assert "print('hello')" in objs[0].text


class TestPdfLoader:
    def test_supports(self, tmp_path):
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4")
        assert PdfLoader().supports(SourceRef(path=str(p)))

    def test_fallback_without_pymupdf(self, tmp_path):
        # Without pymupdf installed, loader falls back to raw text.
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"plain pdf text")
        objs = list(PdfLoader().load(SourceRef(path=str(p))))
        assert len(objs) == 1
        assert objs[0].metadata.get("fallback") is True


class TestGetLoader:
    def test_resolves_markdown(self, sample_markdown):
        loader = get_loader(SourceRef(path=str(sample_markdown)))
        assert isinstance(loader, TextLoader)

    def test_resolves_python(self, sample_python):
        loader = get_loader(SourceRef(path=str(sample_python)))
        assert isinstance(loader, CodeLoader)

    def test_resolves_notebook(self, sample_notebook):
        loader = get_loader(SourceRef(path=str(sample_notebook)))
        assert isinstance(loader, NotebookLoader)

    def test_unknown_returns_none(self, tmp_path):
        p = tmp_path / "file.xyz"
        p.write_text("x")
        assert get_loader(SourceRef(path=str(p))) is None