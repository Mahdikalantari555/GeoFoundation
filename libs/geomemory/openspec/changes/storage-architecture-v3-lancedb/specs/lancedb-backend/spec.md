## Purpose
Embed LanceDB as the primary vector backend, replacing numpy `VectorBackend` as the default.

## ADDED Requirements

### Requirement: LanceBackend implements StorageBackend
The system SHALL provide `LanceBackend` implementing the `StorageBackend` protocol using `pylancedb`. Lance tables stored at `indexes/lancedb/<space_id>.lance/`.

#### Scenario: LanceDB upsert and search
- **WHEN** 100 records are upserted and searched with a query vector
- **THEN** `search` returns top-K `SearchHit` results ordered by cosine similarity descending; latency < 50ms for 10k vectors on commodity hardware.

#### Scenario: Save/load round-trip
- **WHEN** `backend.save(path)` is called then `LanceBackend.load(path, space_id)`
- **THEN** all records and vectors are preserved; `count()` matches original.

### Requirement: Default vector_backend = lancedb
`WorkspaceSettings.vector_backend` default SHALL be `"lancedb"`. Legacy value `"local"` SHALL be treated as `"lancedb"` on settings load, with a rebuild prompt logged.

#### Scenario: New workspace
- **WHEN** a workspace is created with default settings
- **THEN** `vector_backend` is `"lancedb"`; first index build creates Lance table.

#### Scenario: Legacy workspace migration
- **WHEN** a workspace with `vector_backend="local"` is opened
- **THEN** settings are updated to `"lancedb"`; existing numpy index dir preserved until rebuild.
