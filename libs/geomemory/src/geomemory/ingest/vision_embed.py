"""Best-effort OLMoEarth vision embedding after raster persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from geomemory.core.models import IndexManifest
from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import create_manifest

_MAX_TILES_TO_EMBED = 100


def try_embed_vision(
    *,
    conn: sqlite3.Connection,
    revision_id: str,
    vision_path: str | None,
    index_dir: Path | str,
) -> None:
    """Upsert tile previews into ImageIndex when ``vision_path`` is configured.

    If torch/olmoearth_pretrain are unavailable or any step fails, nothing
    propagates — ingest must remain unaffected.
    """
    if not vision_path:
        return

    try:
        embedder = OlmoEarthVisionEmbedder(vision_path)
    except Exception:  # noqa: BLE001 - model may not be installable yet
        return

    scene_row = conn.execute(
        "SELECT id FROM raster_scene WHERE revision_id = ?", (revision_id,)
    ).fetchone()
    if scene_row is None:
        return
    scene_id = str(scene_row["id"])

    tiles = conn.execute(
        "SELECT id, preview_path FROM raster_tile WHERE scene_id = ?", (scene_id,)
    ).fetchall()
    if not tiles:
        return

    preview_paths = [
        str(t["preview_path"]) for t in tiles[:_MAX_TILES_TO_EMBED] if t["preview_path"]
    ]
    if not preview_paths:
        return

    try:
        embeddings = embedder.embed_images(preview_paths)
    except Exception:  # noqa: BLE001 - model may fail at runtime
        return
    if embeddings.shape[0] != len(preview_paths):
        return

    index = _load_image_index(index_dir)
    for i, _ in enumerate(preview_paths):
        tile_id = str(tiles[i]["id"])
        index.upsert(tile_id, embeddings[i])
    _save_image_index(index, index_dir, space_id=embedder.space_id)


def _load_image_index(index_dir: Path | str) -> ImageIndex:
    target = Path(index_dir) / "image"
    try:
        return ImageIndex.load(target)
    except Exception:
        return ImageIndex()


def _save_image_index(
    index: ImageIndex, index_dir: Path | str, *, space_id: str
) -> None:
    target = Path(index_dir) / "image"
    manifest: IndexManifest | None = None
    try:
        from geomemory.index.manifest import load_manifest

        existing = load_manifest(target)
        manifest = create_manifest(
            space_id=existing.space_id or space_id,
            model_id="olmoearth-nano-v1.2",
            dimension=int(index.ids()[0].shape[-1]) if index.ids() else 128,
            doc_count=index.count(),
        )
    except Exception:  # noqa: BLE001
        pass
    if manifest is None:
        manifest = create_manifest(
            space_id=space_id,
            model_id="olmoearth-nano-v1.2",
            dimension=128,
            doc_count=index.count(),
        )
    index.save(target, manifest)
