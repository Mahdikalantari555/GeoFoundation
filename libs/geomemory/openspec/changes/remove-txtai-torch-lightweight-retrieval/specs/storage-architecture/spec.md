## Purpose
Make the storage default lightweight and serverless: SQLite + FTS5 + `sqlite-vec` for vectors, with LanceDB/Qdrant as optional pluggables, and remove the txtai ANN file dependency.

## MODIFIED Requirements

### Requirement: Vector storage — sqlite-vec default, LanceDB/Qdrant optional, PG future
The system SHALL provide a pluggable `VectorBackend` with:
- **Default: sqlite-vec** — embedded vector extension inside SQLite (virtual table `vec_segments`), CPU-only, no server process, co-located with `geomemory.db` so workspace `cp -r` backup remains complete.
- **Optional: LanceDB** — embedded, file-based at `embeddings/lancedb/`, when `vector_backend="lancedb"` is configured.
- **Optional: Qdrant** — when `vector_backend="qdrant"` is configured.
- **Future: PostgreSQL+pgvector+PostGIS** — for server deployment.
ChromaDB SHALL NOT be the default. Vector reads/writes SHALL go through the `VectorBackend`/`RetrievalBackend` protocol, never raw backend clients in callers. No module outside `storage/` or `index/` SHALL import `lancedb`, `qdrant_client`, `sqlite_vec`, or `pgvector` directly — all access via the protocols. `txtai` SHALL NOT be used for vector storage.

#### Scenario: Default without Qdrant/LanceDB
- **WHEN** no vector backend is configured and `sqlite-vec` is installed
- **THEN** text embeddings use `vec_segments` and searches apply metadata filters via SQLite joins, with no external process

#### Scenario: Abstraction holds
- **WHEN** storage code is inspected
- **THEN** no module outside `storage/` or `index/` imports `lancedb`, `qdrant_client`, `sqlite_vec`, or `pgvector` directly

### Requirement: SQLite as source of truth
*(unchanged in intent, updated for vec table)* SQLite (WAL, `foreign_keys=ON`) remains authoritative for `documents, chunks, assets, collections, citations, embeddings_metadata, tags, spatial_metadata`. Database SHALL store document/chunk metadata, asset locations, timestamps, sensor info, collection membership, citations, provenance, plus `embeddings_metadata`/`IndexManifest` (`space_id`, `model_id`, `dimension=384`, checksum). Vectors SHALL be stored either in `vec_segments` (sqlite-vec) or the configured optional backend (LanceDB/Qdrant); GeoTIFF binaries, large imagery, and Parquet datasets SHALL NOT be stored in SQLite.

#### Scenario: Vectors in vec table
- **WHEN** `ONNXEmbeddingProvider` embeds 384-d vectors and `SqliteVecBackend.upsert` is called
- **THEN** rows appear in `vec_segments` with `id` PK and `embedding[384]`, and `embeddings_metadata` records the manifest with `dimension=384`

### Requirement: Embedding layer — ONNX canonical, llama.cpp legacy/optional, torch isolated to vision
Text embeddings SHALL default to `ONNXEmbeddingProvider` (`Xenova/all-MiniLM-L6-v2`, 384-d, quantized `onnx/model_quantized.onnx`, L2-normalized) via `EmbeddingProvider`; `llama-cpp-python` (GGUF) SHALL be retained as a legacy, optional backend for offline/air-gapped use, not the default. `torch` SHALL be reachable only via opt-in `[vision]` (OLMoEarth Nano) and SHALL NOT be pulled by the default install. Heavy deps SHALL remain optional extras imported lazily. Embedding spaces SHALL stay isolated per modality (`text.*` vs vision).

#### Scenario: Default text embedding is ONNX quantized
- **WHEN** `embedding_provider` is unset and text is embedded
- **THEN** the system uses `Xenova/all-MiniLM-L6-v2` via `onnxruntime` with `onnx/model_quantized.onnx`, reporting `space_id=text.onnx.Xenova-all-MiniLM-L6-v2.v1` and 384-d L2-normalized vectors

#### Scenario: Vision still works opt-in
- **WHEN** `geomemory[vision]` is installed and `vision_path` points to an OLMoEarth `.pth`
- **THEN** vision embedding succeeds via torch, while `pip install geomemory` without `[vision]` never installs torch

## ADDED Requirements

### Requirement: Lightweight runtime dependencies
Base runtime dependencies SHALL be `numpy`, `onnxruntime`, `tokenizers`, `sqlite-vec`, `pydantic`, `pandas`, `geopandas`, `shapely`, `pyarrow`, `huggingface-hub`, `PyYAML`, `click`. The distributions `txtai`, `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, `safetensors` SHALL NOT appear in the transitive graph of `pip install geomemory` (plain). The `vision` extra may reintroduce `torch` intentionally; no other extra SHALL pull it.

#### Scenario: Dependency gate
- **WHEN** CI runs `pip install geomemory && pipdeptree | grep -qiE "torch|txtai|sentence-transformers"`
- **THEN** the grep finds no matches and the job passes

### Requirement: Reindex utility and migration docs
The system SHALL provide `geomemory reindex --workspace <path> [--collection <id>] [--provider onnx] [--model Xenova/all-MiniLM-L6-v2]` that rebuilds the dense index from `segment` rows via the current `EmbeddingProvider`, replaces `vec_segments` contents, and writes a fresh `IndexManifest`. A migration document `docs/migration-txtai-to-onnx.md` SHALL describe the upgrade path (`pip uninstall txtai torch ...`, `pip install geomemory[onnx,sqlite-vec]`, run `reindex`, verify `pipdeptree`). Opening a workspace whose manifest `space_id` starts with `text.st.*` or `text.txtai.*` SHALL emit a `ReindexRequired` warning naming both old and new `space_id`.

#### Scenario: Legacy index warns
- **WHEN** a workspace with a `text.st.*` manifest is opened after the change and `search` is called without rebuilding
- **THEN** a warning is emitted naming the old and new space ids and suggesting `geomemory reindex`
