# Tasks: storage-architecture-v3-lancedb

- [x] Task 1: Add `pylancedb` optional extra
  - Acceptance: `pyproject.toml` adds `lancedb = ["pylancedb>=0.5"]`; `pip install geomemory[lancedb]` works; existing installs unaffected.
  - Verify: `conda run -n geospatial pip install -e libs/geomemory[lancedb]` succeeds in clean venv.
  - Files: `libs/geomemory/pyproject.toml`

- [x] Task 2: Implement `LanceBackend`
  - Acceptance: implements `StorageBackend` protocol; `upsert` writes Lance table; `search` returns `SearchHit` list with cosine similarity; `save`/`load`/`exists` work; 384-dim float32 vectors.
  - Verify: unit tests: upsert 100 records, search top-5, assert ordering; save/load round-trip; exists on missing dir returns False.
  - Files: `src/geomemory/index/lance_backend.py`, `tests/unit/test_lance_backend.py`

- [x] Task 3: Unified `StorageBackend` interface
  - Acceptance: `StorageBackend` protocol defined; `VectorBackend`, `QdrantBackend`, `LanceBackend` all implement it; `IndexService` dispatches via factory.
  - Verify: `mypy --strict` passes for all backend files; unit test factory returns correct backend per `vector_backend` setting.
  - Files: `src/geomemory/index/storage_backend.py`, `src/geomemory/index/vector_backend.py`, `src/geomemory/index/qdrant_backend.py`, `src/geomemory/services/index_service.py`, `tests/unit/test_storage_backend.py`

- [x] Task 4: Change default `vector_backend`
  - Acceptance: `WorkspaceSettings.vector_backend` default changes from `"local"` to `"lancedb"`; `"numpy"` added as legacy fallback; existing workspaces with `vector_backend="local"` auto-migrate to `"lancedb"` on settings load (with rebuild prompt).
  - Verify: new workspace gets `lancedb`; old workspace opens with `local` → settings updated to `lancedb`; rebuild index produces Lance table.
  - Files: `src/geomemory/core/models.py`, `src/geomemory/core/config.py`

- [x] Task 5: AssetLayout abstraction
  - Acceptance: `AssetLayout` maps logical paths to content-addressed store; `Asset.path` stores logical path; `layout.resolve(hash)` returns physical path.
  - Verify: unit tests for all asset kinds; round-trip logical→physical→logical.
  - Files: `src/geomemory/storage/asset_layout.py`, `tests/unit/test_asset_layout.py`

- [x] Task 6: Wire AssetLayout into Workspace
  - Acceptance: `Workspace` initializes `AssetLayout`; ingest stores assets via layout; retrieval resolves asset paths via layout.
  - Verify: integration test: ingest document → asset path is logical → resolved to objects/<sha256>.
  - Files: `src/geomemory/core/workspace.py`, `tests/integration/test_asset_layout.py`

- [x] Task 7: Gates
  - Acceptance: full suite green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests server/tests -q && conda run -n geospatial ruff check libs/geomemory/src server/src && conda run -n geospatial mypy --strict libs/geomemory/src/geomemory`

Dependencies: 1→2, 2→3, 3→4, 5→6, all→7.
