"""Ingestion pipeline: load → parse → chunk → store → index."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from geomemory.core.events import ASSET_CREATED, DomainEvent, EventBus
from geomemory.core.exceptions import CollectionNotFoundError, UnsupportedFormatError
from geomemory.core.hashing import sha256_bytes
from geomemory.core.models import (
    Asset,
    AssetRevision,
    ParsedObject,
    Segment,
    SourceRef,
)
from geomemory.ingest.chunkers import DEFAULT_CHUNKER, default_registry as default_chunker_registry
from geomemory.ingest.loaders import default_registry as default_loader_registry, get_loader
from geomemory.ingest.loaders.base import mime_for_path
from geomemory.storage.object_store import ObjectStore


class IngestionPipeline:
    """Orchestrate the full ingestion flow for a single source.

    Steps: hash → dedup → load → chunk → store raw bytes → persist asset,
    revision, and segments → emit events. Optional embedding/indexing is
    handled by the service layer.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        objects: ObjectStore,
        *,
        events: EventBus | None = None,
        chunker_name: str = DEFAULT_CHUNKER,
        parser_version: str = "0.1.0",
        artifact_dir: str | Path | None = None,
    ) -> None:
        self.conn = conn
        self.objects = objects
        self.events = events or EventBus()
        self.chunker_name = chunker_name
        self.parser_version = parser_version
        self.artifact_dir = Path(artifact_dir) if artifact_dir else None

    def ingest_source(self, source: SourceRef, collection_id: str) -> dict[str, Any]:
        """Ingest a single source into a collection. Returns a result dict."""
        # Validate collection.
        row = self.conn.execute(
            "SELECT id FROM collection WHERE id = ? AND archived = 0", (collection_id,)
        ).fetchone()
        if row is None:
            raise CollectionNotFoundError(f"Collection not found: {collection_id}")

        # Read raw bytes.
        if source.content_bytes is not None:
            raw = source.content_bytes
        elif source.path is not None:
            raw = Path(source.path).read_bytes()
        else:
            raise ValueError("SourceRef has no local content")

        content_hash = sha256_bytes(raw)

        # Dedup: reuse existing revision with same hash.
        existing = self.conn.execute(
            "SELECT * FROM asset_revision WHERE hash = ? LIMIT 1", (content_hash,)
        ).fetchone()
        if existing is not None:
            return {
                "asset_id": existing["asset_id"],
                "revision_id": existing["id"],
                "skipped": True,
                "reason": "duplicate hash",
            }

        # Resolve loader.
        loader = self._resolve_loader(source)
        if loader is None:
            raise UnsupportedFormatError(
                f"No loader supports source: {source.path or '<bytes>'}"
            )

        # Load + chunk.
        parsed_objects = list(loader.load(source))
        if not parsed_objects:
            raise UnsupportedFormatError("Loader produced no parsed objects")

        chunker_registry = default_chunker_registry()
        chunker = chunker_registry.get(self.chunker_name)
        if chunker is None:
            raise ValueError(f"Unknown chunker: {self.chunker_name}")

        segments: list[Segment] = []
        for parsed in parsed_objects:
            for draft in chunker.split(parsed):
                segments.append(
                    Segment(
                        revision_id="",  # set after revision created
                        segment_type=draft.segment_type,
                        text=draft.text,
                        locator=draft.locator,
                        parent_section_id=draft.parent_section_id,
                        neighbor_ids=draft.neighbor_ids,
                        metadata=draft.metadata,
                    )
                )

        # Store raw bytes.
        stored_hash = self.objects.put_bytes(raw)
        assert stored_hash == content_hash

        # Determine kind from mime.
        mime_type = parsed_objects[0].mime_type
        kind = _kind_for_mime(mime_type)

        # Persist asset + revision.
        title = Path(source.path).name if source.path else parsed_objects[0].title
        asset = Asset(collection_id=collection_id, kind=kind, title=title)
        revision = AssetRevision(
            asset_id=asset.id,
            hash=content_hash,
            mime_type=mime_type,
            size_bytes=len(raw),
            parser_version=self.parser_version,
        )
        self.conn.execute(
            "INSERT INTO asset (id, collection_id, kind, title, current_revision_id, deleted_at, created_at, metadata) "
            "VALUES (?, ?, ?, ?, NULL, NULL, ?, ?)",
            (asset.id, asset.collection_id, asset.kind, asset.title, asset.created_at, json.dumps(asset.metadata)),
        )
        self.conn.execute(
            "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version, ingested_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision.id,
                revision.asset_id,
                revision.hash,
                revision.mime_type,
                revision.size_bytes,
                revision.parser_version,
                revision.ingested_at,
                json.dumps(revision.metadata),
            ),
        )

        # Persist segments.
        segment_ids: list[str] = []
        for segment in segments:
            segment.revision_id = revision.id
            self.conn.execute(
                "INSERT INTO segment (id, revision_id, segment_type, text, locator, parent_section_id, neighbor_ids, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    segment.id,
                    segment.revision_id,
                    segment.segment_type,
                    segment.text,
                    json.dumps(segment.locator),
                    segment.parent_section_id,
                    json.dumps(segment.neighbor_ids),
                    json.dumps(segment.metadata),
                    segment.created_at,
                ),
            )
            segment_ids.append(segment.id)

        # Persist raster scenes / vector layers and their spatial index entries.
        for parsed in parsed_objects:
            raster_payload = parsed.metadata.get("raster")
            vector_payload = parsed.metadata.get("vector")
            if raster_payload is not None:
                from geomemory.rs.persist import persist_scene, spatial_metadata

                scene = persist_scene(
                    self.conn,
                    revision.id,
                    raster_payload["scene"],
                    tiles=raster_payload.get("tiles"),
                )
                self._attach_spatial_metadata(
                    segment_ids,
                    spatial_metadata(
                        bbox=scene.bbox,
                        acquired_at=scene.acquired_at,
                        sensor=scene.sensor,
                    ),
                )
            if vector_payload is not None:
                from geomemory.rs.persist import persist_vector_layer, spatial_metadata

                layer = persist_vector_layer(self.conn, revision.id, vector_payload["layer"])
                self._attach_spatial_metadata(
                    segment_ids, spatial_metadata(bbox=layer.metadata.get("bbox") or [])
                )

        self.conn.execute(
            "UPDATE asset SET current_revision_id = ? WHERE id = ?", (revision.id, asset.id)
        )
        self.conn.commit()

        self.events.emit(
            DomainEvent(
                event_type=ASSET_CREATED,
                entity_id=asset.id,
                payload={
                    "revision_id": revision.id,
                    "hash": content_hash,
                    "mime_type": mime_type,
                    "segment_count": len(segments),
                },
            )
        )

        return {
            "asset_id": asset.id,
            "revision_id": revision.id,
            "segment_count": len(segments),
            "skipped": False,
        }

    def ingest_batch(self, sources: list[SourceRef], collection_id: str) -> dict[str, Any]:
        """Ingest multiple sources, continuing past individual failures."""
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for source in sources:
            try:
                results.append(self.ingest_source(source, collection_id))
            except Exception as exc:  # noqa: BLE001 - batch boundary
                errors.append({"source": str(source.path or "<bytes>"), "error": str(exc)})
        return {"results": results, "errors": errors, "success_count": len(results), "error_count": len(errors)}

    def _resolve_loader(self, source: SourceRef) -> Any:
        """Return a loader for the source, honoring rs asset artifact output."""
        mime = mime_for_path(source.path or "") if source.path else None
        if mime in ("image/tiff", "image/geotiff"):
            from geomemory.ingest.loaders.geotiff import GeoTiffLoader

            return GeoTiffLoader(artifact_dir=self.artifact_dir)
        if mime == "application/geo+json":
            from geomemory.ingest.loaders.geojson import GeoJsonLoader

            return GeoJsonLoader()
        return get_loader(source, default_loader_registry())

    def _attach_spatial_metadata(
        self, segment_ids: list[str], spatial: dict[str, Any]
    ) -> None:
        """Merge a spatial payload into the metadata of the given segments."""
        for segment_id in segment_ids:
            row = self.conn.execute(
                "SELECT metadata FROM segment WHERE id = ?", (segment_id,)
            ).fetchone()
            if row is None:
                continue
            try:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            meta["spatial"] = {**meta.get("spatial", {}), **spatial}
            self.conn.execute(
                "UPDATE segment SET metadata = ? WHERE id = ?",
                (json.dumps(meta), segment_id),
            )


def _kind_for_mime(mime_type: str) -> str:
    if mime_type.startswith("text/"):
        return "document"
    if mime_type in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        return "document"
    if mime_type in ("text/x-python", "text/javascript"):
        return "code"
    if mime_type in ("image/tiff", "image/geotiff"):
        return "raster"
    if mime_type == "application/geo+json":
        return "vector"
    if mime_type == "text/csv":
        return "table"
    return "document"