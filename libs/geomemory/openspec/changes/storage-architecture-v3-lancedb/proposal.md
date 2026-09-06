# Proposal: storage-architecture-v3-lancedb

## Why

GeoMemory's current vector storage has two issues:

1. **No primary embedded vector backend**: `VectorBackend` (`records.json` + `embeddings.npy`) is a minimal on-disk numpy format. It lacks ANN optimization, metadata filtering, and efficient scaling beyond small workspaces. Qdrant is available but introduces a server process — overkill for local-first single-user use.
2. **No unified storage abstraction**: `VectorBackend`, `QdrantBackend`, and `ObjectStore` are separate interfaces with no common `StorageBackend` seam. Future migration to LanceDB or other backends requires scattered changes.

LanceDB is the right v3 default: embedded, file-based, no server, optimized for vector workloads, supports metadata filtering and efficient ANN search — exactly matching the v2/v3 proposal.

## What Changes

### LanceDB Vector Backend (new primary)
- Add `geomemory[index/lance_backend.py]` implementing `VectorBackend` protocol using `pylancedb`.
- Default `vector_backend="lancedb"` in `WorkspaceSettings`; local numpy backend becomes fallback.
- Storage under `indexes/lancedb/<space_id>.lance/`.
- Supports cosine similarity, metadata filtering, and efficient upsert/search.

### Unified StorageBackend Interface
- Introduce `StorageBackend` protocol in `geomemory[index/storage_backend.py]`.
- `VectorBackend` renamed/adapted to implement `StorageBackend`.
- `LanceBackend` and `QdrantBackend` both implement `StorageBackend`.
- `IndexService` dispatches via factory `build_storage_backend(settings, space_id)`.

### Asset Layout Restructure
- Introduce `AssetLayout` abstraction in `geomemory/storage/asset_layout.py`.
- Logical paths: `assets/documents/`, `assets/imagery/`, `assets/vectors/`, `assets/datasets/`.
- Backed by existing `ObjectStore` (content-addressed); layout provides human-readable directory names.
- `Asset.path` becomes logical path; `ObjectStore` resolves to content-addressed hash path.

### Deprecate Qdrant as default
- `vector_backend` enum: `local` (LanceDB) | `qdrant` (optional server).
- Qdrant path remains functional but is no longer the recommended vector backend.
- Docker images include `pylancedb` by default; Qdrant requires explicit `pip install geomemory[vector]`.

## Capabilities

### New Capabilities
- `lancedb-backend`: embedded LanceDB vector backend with ANN + metadata filtering.
- `storage-abstraction`: unified `StorageBackend` interface for vector backends.
- `asset-layout`: logical asset directory layout over content-addressed store.

### Modified Capabilities
- `vector-search`: LanceDB becomes default; local numpy fallback remains.
- `workspace-management`: `vector_backend` enum updated; migration path documented.

## Impact

- **Code**: `src/geomemory/index/lance_backend.py` (new), `src/geomemory/index/storage_backend.py` (new), `src/geomemory/index/vector_backend.py` (adapt), `src/geomemory/index/qdrant_backend.py` (implement interface), `src/geomemory/core/models.py` (vector_backend default), `src/geomemory/storage/asset_layout.py` (new), `src/geomemory/core/workspace.py` (layout wiring).
- **APIs**: no breaking changes; `vector_backend` enum value changes from `local` to `lancedb` (local numpy still reachable via fallback).
- **Deps**: new optional `geomemory[lancedb]` (`pylancedb>=0.5`); included in default install.
- **Risks**: LanceDB API stability; migration of existing `embeddings.npy` indexes to LanceDB format (offline rebuild acceptable).
