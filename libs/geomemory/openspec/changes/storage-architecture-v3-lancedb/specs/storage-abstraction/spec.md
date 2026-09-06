## Purpose
Define a unified `StorageBackend` protocol so all vector backends share one interface.

## ADDED Requirements

### Requirement: StorageBackend protocol
The system SHALL define `StorageBackend` protocol with methods:
`upsert(records, embeddings)`, `search(request) -> list[SearchHit]`, `count() -> int`,
`save(path)`, `load(path, space_id) -> StorageBackend`, `exists(path) -> bool`.

#### Scenario: Protocol conformance
- **WHEN** `VectorBackend`, `LanceBackend`, and `QdrantBackend` are instantiated
- **THEN** all pass `isinstance(..., StorageBackend)` structural check; `IndexService` dispatches without type branches.

### Requirement: Factory dispatch
`IndexService._storage_backend(space_id)` SHALL return the correct backend based on `settings.vector_backend`:
- `"lancedb"` → `LanceBackend`
- `"qdrant"` → `QdrantBackend`
- `"numpy"` / `"local"` → `VectorBackend` (legacy)

#### Scenario: Factory returns LanceBackend
- **WHEN** settings.vector_backend == "lancedb"
- **THEN** `_storage_backend()` returns `LanceBackend` instance for the space.
