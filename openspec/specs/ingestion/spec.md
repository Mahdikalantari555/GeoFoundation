# Ingestion — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Purpose

Ingestion turns raw sources (files or bytes) into immutable revisions of assets with searchable segments, preserving provenance from bytes to chunks.

## Requirements

### Requirement: Source acceptance
The facade SHALL accept `str` paths, `Path` objects, or raw `bytes` for ingestion into an existing collection.

#### Scenario: File ingest
- **WHEN** `ingest("paper.pdf", collection_id=...)` is called
- **THEN** bytes are read, hashed, parsed, chunked, stored, and a completed `Job` is returned

#### Scenario: Unknown collection
- **WHEN** collection id does not exist
- **THEN** `CollectionNotFoundError` is raised before any write

### Requirement: Content-addressed deduplication
Ingestion SHALL skip processing when the SHA-256 of the source already exists as an asset revision.

#### Scenario: Duplicate hash
- **WHEN** the same file is ingested twice into any collection
- **THEN** the second call returns a completed job marked `skipped` with reason "duplicate hash"

### Requirement: Format routing
The system SHALL detect MIME type by extension and route to loaders: text, code, PDF (pymupdf), GeoJSON, GeoTIFF — producing typed segments (`paragraph`, `table`, `formula`, `code_unit`, `heading`, `cell`).

#### Scenario: Document chunking
- **WHEN** a text/PDF/code source is ingested
- **THEN** header-preserving or fixed-size chunking produces segments with locators

#### Scenario: Unsupported format
- **WHEN** MIME/kind cannot be resolved
- **THEN** `UnsupportedFormatError` is raised

### Requirement: Immutable revisions
Each ingest SHALL create one asset plus one revision stamped with hash, mime, size, parser_version; the asset's `current_revision_id` points at it.

#### Scenario: Revision recorded
- **WHEN** ingestion completes
- **THEN** `asset_revision` contains a UNIQUE (asset, hash) row and raw bytes live at `objects/<sha256>`

### Requirement: Spatial payload persistence
Raster/vector sources SHALL additionally produce `raster_scene`(+tiles) or `vector_layer` rows and RTree entries.

#### Scenario: GeoTIFF ingest
- **WHEN** a .tif is ingested (with `rs` extra installed)
- **THEN** scene metadata (EPSG crs, bbox, sensor, acquired_at) and tiles persist with spatial index rows

### Requirement: Job accounting
Every ingest SHALL be representable as a `Job`; the ingestion service can enqueue jobs in `pending` state for later execution.

#### Scenario: Service submission
- **WHEN** `IngestionService.ingest()` is called
- **THEN** a pending job row exists retrievable via `get_job`
