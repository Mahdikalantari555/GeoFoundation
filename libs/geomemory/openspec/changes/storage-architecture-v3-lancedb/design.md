# Design: storage-architecture-v3-lancedb

## Context

Current vector storage: `VectorBackend` (numpy + JSON on disk) and `QdrantBackend`
(remote server). `VectorBackend` is the default `local` backend; it works but lacks
ANN optimization and metadata filtering. Qdrant is powerful but requires a running
server — mismatched with GeoMemory's local-first, zero-infra goal.

The v2/v3 proposal recommended LanceDB as the embedded vector backend.

## Goals / Non-Goals

- Goals: LanceDB as default embedded vector backend; unified `StorageBackend` interface;
  logical asset layout over content-addressed store; backward compatibility.
- Non-Goals: multi-user vector sharing, remote LanceDB, distributed LanceDB, migration automation (manual rebuild acceptable).

## Decisions

### D1. LanceDB as default vector backend
`vector_backend` enum changes: `"lancedb"` (default) | `"qdrant"` | `"numpy"` (legacy fallback).
`IndexService._storage_backend()` factory returns `LanceBackend` for `lancedb`,
`QdrantBackend` for `qdrant`, `VectorBackend` for `numpy`.

Lance table URI: `indexes/lancedb/<space_id>.lance/`.
Schema: vector (float32[], 384 dim), id (str), metadata (JSON).

### D2. Unified StorageBackend interface
```python
class StorageBackend(Protocol):
    def upsert(self, records: list[IndexRecord], embeddings: np.ndarray) -> None: ...
    def search(self, request: SearchRequest) -> list[SearchHit]: ...
    def count(self) -> int: ...
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path, space_id: str) -> StorageBackend: ...
    @classmethod
    def exists(cls, path: Path) -> bool: ...
```
All three backends implement this. `IndexService` never branches on backend type.

### D3. AssetLayout abstraction
`AssetLayout` maps logical asset kinds to content-addressed paths:
- `assets/documents/<sha256_prefix>/<sha256>` → `objects/sha256/ab/cd/<sha256>`
- `assets/imagery/...`, `assets/vectors/...`, `assets/datasets/...`
`ObjectStore` handles content addressing; `AssetLayout` provides human-readable paths.
`Asset.path` stores logical path; resolution via `layout.resolve(asset_hash)`.

### D4. pylancedb dependency
Add optional `geomemory[lancedb]` extra: `pylancedb>=0.5`.
Included in default `pip install geomemory[ai]` and Docker images.
Qdrant remains `geomemory[vector]` optional.

### D5. Migration
Existing `indexes/<space_id>/` (numpy format) is detected on open; user prompted to
rebuild. No automatic migration; `ws.rebuild_index(space_id)` converts to Lance.

## Risks / Trade-offs

- [LanceDB API churn] → pin `pylancedb>=0.5,<1.0`; abstract interface isolates changes.
- [Existing index rebuild] → user-initiated rebuild; old `indexes/*/` dirs preserved until manually removed.
