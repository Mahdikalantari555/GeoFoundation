"""Index manifest creation and validation."""

from __future__ import annotations

import json
from pathlib import Path

from geomemory.core.models import IndexManifest


def write_manifest(index_dir: str | Path, manifest: IndexManifest) -> Path:
    """Write a manifest.json into an index directory."""
    target = Path(index_dir) / "manifest.json"
    target.write_text(manifest.to_json(), encoding="utf-8")
    return target


def load_manifest(index_dir: str | Path) -> IndexManifest:
    """Load manifest.json from an index directory."""
    target = Path(index_dir) / "manifest.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    return IndexManifest(**data)


def manifest_exists(index_dir: str | Path) -> bool:
    """Return True if the index directory has a manifest."""
    return (Path(index_dir) / "manifest.json").is_file()


def create_manifest(
    *,
    space_id: str,
    model_id: str,
    dimension: int,
    model_revision: str = "",
    normalization: str = "l2",
    chunker: str = "header_then_token",
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
    doc_count: int = 0,
) -> IndexManifest:
    """Build an IndexManifest with defaults."""
    return IndexManifest(
        space_id=space_id,
        model_id=model_id,
        model_revision=model_revision,
        dimension=dimension,
        normalization=normalization,
        chunker=chunker,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        doc_count=doc_count,
    )
