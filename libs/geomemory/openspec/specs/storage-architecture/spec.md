# Storage Architecture — Specification

Local-first, file-first research memory for Remote Sensing and GeoAI. Zero-config single-user operation supporting documents, code, notes, and geospatial assets with multimodal embeddings, efficient semantic search, easy backup/portability, and optional scale-out — with no mandatory external services.

## Requirements

### Requirement: Local-first, file-first layout
The workspace SHALL be a self-contained directory with the authoritative state in `geomemory.db` and large assets on disk:
```
geomemory/
├── geomemory.db
├── assets/{documents,code,imagery,vectors,datasets}
├── embeddings/lancedb/
└── cache/
```
Database SHALL store metadata and references only; file blobs SHALL remain on disk for portability and backup.

#### Scenario: Fresh workspace
- **WHEN** a new workspace is created
- **THEN** `geomemory.db` is initialized (WAL, FK, migrations) and `assets/`, `embeddings/lancedb/`, `cache/` exist as empty directories

#### Scenario: Backup is file copy
- **WHEN** a user copies the workspace directory
- **THEN** all documents, imagery, and embeddings remain restorable without an external dump

### Requirement: SQLite as source of truth
SQLite (WAL, `foreign_keys=ON`) SHALL be the authoritative metadata store for `documents, chunks, assets, collections, citations, embeddings_metadata, tags, spatial_metadata`. It SHALL store document/chunk metadata, asset locations, timestamps, sensor info, collection membership, citations, and provenance. It SHALL NOT store GeoTIFF binaries, large imagery, Parquet datasets, or raw embedding vectors.

#### Scenario: Metadata lives in SQLite
- **WHEN** a GeoTIFF `assets/imagery/landsat_2025_001.tif` is ingested
- **THEN** SQLite holds `{id, path, sensor, acquisition_time, bbox, bands, resolution, embedding_id}` while the `.tif` bytes remain on disk under `assets/imagery/`

#### Scenario: Vectors not in SQLite
- **WHEN** text or OLMoEarth embeddings are built
- **THEN** vectors are persisted in the configured vector backend (default LanceDB) and only their `embedding_id`, `space_id`, and manifest are recorded in SQLite

### Requirement: Full-text search via FTS5
FTS5 (`segments_fts`) SHALL provide keyword/BM25/phrase search over chunks and SHALL stay in sync with the `segment` table via triggers, with no Elasticsearch dependency.

#### Scenario: BM25 query
- **WHEN** a user searches "crop stress"
- **THEN** FTS5 returns BM25-ranked chunk hits that map to asset locators with provenance

#### Scenario: Sparse index integrity
- **WHEN** a segment is inserted/updated/deleted
- **THEN** the FTS index reflects it without manual sync

### Requirement: Lightweight spatial metadata in SQLite
SQLite SHALL store per-asset spatial metadata (`bbox_minx/miny/maxx/maxy, epsg` or `geometry_wkt`) and support bbox filtering and AOI overlap checks without a spatial engine.

#### Scenario: Bbox filter
- **WHEN** a search supplies `bbox=[...]`
- **THEN** only assets whose stored bbox intersects are returned

#### Scenario: Temporal-spatial filter
- **WHEN** a query combines spatial bbox with acquisition time range
- **THEN** filtering applies on SQLite metadata before vector re-ranking

### Requirement: Raster asset strategy — files stay external
GeoTIFF scenes SHALL remain as external files under `assets/imagery/`; SQLite SHALL keep only the asset record and spatial/sensor metadata. Embedding for a raster SHALL be derived via the configured vision model and stored in the vector backend.

#### Scenario: Raster ingest
- **WHEN** `assets/imagery/scene.tif` is ingested
- **THEN** its row records `path, bbox, epsg, sensor, bands, resolution` and its OLMoEarth embedding is stored in `embeddings/lancedb/` under the vision space

### Requirement: Vector storage — LanceDB default, Qdrant optional, PG future
The system SHALL provide a pluggable `VectorBackend` with:
- **Default: LanceDB** — embedded, file-based, ANN with metadata filtering at `embeddings/lancedb/`, no server process.
- **Optional: Qdrant** — when configured, without requiring users to think about collections or deployment.
- **Future: PostgreSQL+pgvector+PostGIS** — for server deployment.
ChromaDB SHALL NOT be the default. Vector reads/writes SHALL go through the `VectorBackend` interface, never raw backend clients in callers.

#### Scenario: Default without Qdrant
- **WHEN** no vector backend is configured
- **THEN** text and OLMoEarth embeddings use LanceDB under `embeddings/lancedb/` and searches apply metadata filters there

#### Scenario: Qdrant opt-in
- **WHEN** `vector_backend=qdrant` is configured
- **THEN** embeddings route to Qdrant while SQLite metadata and FTS5 remain unchanged, with no change to caller code beyond config

#### Scenario: Abstraction holds
- **WHEN** storage code is inspected
- **THEN** no module outside `storage/` or `index/` imports `lancedb`, `qdrant_client`, or `pgvector` directly — all access is via `StorageBackend`/`VectorBackend`/`AssetBackend` protocols

### Requirement: Design principles and non-goals
The architecture SHALL uphold local-first, file-first, SQLite-as-source-of-truth, pluggable vector backends, storage abstraction from day one, and no mandatory external services. Multi-tenant SaaS, distributed DBs, cluster deployment, and always-on servers are explicitly non-goals for the default installation.

#### Scenario: Zero mandatory services
- **WHEN** a user installs the default `geomemory` package and creates a workspace
- **THEN** no Redis, Elasticsearch, MongoDB, Qdrant, Pinecone, or PostgreSQL process is required

### Requirement: Embedding layer — sentence-transformers default, llama.cpp legacy/optional
Text embeddings SHALL default to `sentence-transformers` (dense, easy to install/run); `llama-cpp-python` (GGUF) SHALL be retained as a **legacy, optional** backend for offline/air-gapped use, not the default. Heavy deps SHALL remain optional extras imported lazily. Embedding spaces SHALL stay isolated per modality (`text.*` vs vision).

#### Scenario: Default text embedding
- **WHEN** `embedding_backend` is unset and text is embedded
- **THEN** the system uses `sentence-transformers/all-MiniLM-L6-v2` (or the ONNX variant when `onnx` is selected) with L2-normalized vectors

#### Scenario: Legacy llama.cpp still works when installed
- **WHEN** `embedding_backend=llamacpp` is selected and `llama-cpp-python` plus a GGUF model are present
- **THEN** embedding succeeds via the GGUF path, but the install docs and Doctor mark it as legacy/optional

#### Scenario: Lazy optional imports
- **WHEN** `geomemory` is imported without the `[st]` or `[llamacpp]` extras
- **THEN** no `sentence_transformers` or `llama_cpp` import occurs at import time; a clear error naming the missing extra is raised only when that backend is invoked

### Requirement: Future scaling path
The storage interfaces SHALL allow migration without caller rewrites across: v1 `SQLite+FTS5` (documents), v2 `+LanceDB` (text+image vectors), v3 `+spatial metadata` (remote-sensing ready), v4 `PostgreSQL+pgvector+PostGIS` (server). The recommended default SHALL remain `SQLite+FTS5+LanceDB+file asset store`.

#### Scenario: v1→v2 upgrade
- **WHEN** a v1 workspace (documents only) is opened with LanceDB available
- **THEN** existing FTS5 and assets continue to work and new vector indexes are created under `embeddings/lancedb/` without migration of the document store
