# ADR-0003: Storage Architecture — single SQLite + content-addressed object store

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

GeoMemory must store: structured metadata (assets/revisions/segments), full-text searchable text, spatial bboxes, conversation/QA audit logs, feedback — while remaining a copy-the-folder portable research tool with zero services.

## Decision

**One SQLite database** (`workspace/geomemory.db`) + **one filesystem object store** (`workspace/objects/ab/cd/<sha256>`):

- WAL mode; `PRAGMA foreign_keys = ON`; schema initialized from `storage/schema.sql` v1.
- **FTS5** virtual table (`segments_fts`, external-content, unicode61 tokenizer) with insert/delete/update triggers on `segment` → sparse search without a separate index process.
- **RTree** virtual table (`spatial_index`: min/max lat/lon) fed through `spatial_entity` mapping table (TEXT entity ids ↔ integer rowids).
- Provenance chain enforced by FKs: `asset → asset_revision(UNIQUE(asset_id, hash)) → segment → citation`; raw bytes addressed by SHA-256 and immutable.
- Typed repositories (`storage/repositories/*`) wrap raw parameterized SQL; migrations tracked in `schema_migration` via `storage/migrations.py`.
- Vector indexes live as files beside the DB (`indexes/<space>/`) with JSON manifests — not in SQLite.

## Consequences

- ✅ Entire deployment state = one directory; backup/restore is a file copy.
- ✅ FTS5+RTree give sparse & spatial query capability with no extra infrastructure.
- ✅ Content-addressing makes ingest idempotent (duplicate hash short-circuit) and dedupe-friendly.
- ❌ Single-writer ceiling; concurrent writers across processes risk `SQLITE_BUSY` (unhandled retry logic today).
- ❌ RTree is bbox-only (no geometry ops); complex spatial predicates stay in Python post-filtering.
- ❌ Large blobs in `objects/` are never garbage-collected when assets are deleted (soft-delete only).
