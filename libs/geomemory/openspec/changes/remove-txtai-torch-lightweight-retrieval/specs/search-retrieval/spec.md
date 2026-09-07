## Purpose
Remove the txtai ANN dependency from retrieval; dense search runs via `sqlite-vec` (preferred) or pluggable Qdrant/LanceDB, fused with FTS5 via RRF, with no coupling to the embedding inference engine.

## MODIFIED Requirements

### Requirement: Hybrid search
The system SHALL combine sparse (SQLite FTS5 `segments_fts`) and dense (vector backend) results using Reciprocal Rank Fusion by default; `sparse`, `dense`, and linear-fusion modes SHALL be selectable. The dense backend SHALL be `SqliteVecBackend` (sqlite-vec) by default when available, with `QdrantBackend` and `LanceBackend` as pluggable alternatives via the `VectorBackend` abstraction; `NumpyBackend` SHALL remain as the pure-numpy fallback when `sqlite-vec` is not loadable. The system SHALL NOT require or import `txtai` for any search mode.

#### Scenario: Hybrid query via sqlite-vec
- **WHEN** `search(query)` runs with `SqliteVecBackend` configured and both FTS5 and vec tables populated
- **THEN** hits from both engines are fused via `retrieval/fusion.rrf_fuse`, deduplicated, diversity-capped (max 3 per document), and truncated to `top_n`, and dense scores derive from `sqlite-vec` cosine

#### Scenario: Fallback without sqlite-vec
- **WHEN** the `sqlite-vec` extension is not installed or fails to load
- **THEN** the system falls back to `NumpyBackend` for dense scoring (keyword-only degradation) and Doctor reports `sqlite_vec.loadable=false`, never crashing search

#### Scenario: No txtai import
- **WHEN** the codebase is grepped for `import txtai` / `from txtai` and `index/txtai_backend.py` is checked
- **THEN** no matches exist and `index/txtai_backend.py` is absent

## ADDED Requirements

### Requirement: Dense vector storage via sqlite-vec
The system SHALL persist dense text embeddings in a `sqlite-vec` virtual table (`vec_segments` or equivalent `vec0` table) with `embedding[384] float` and `id` primary key, inside the workspace database file (or sibling `.vec` file that stays with `geomemory.db` for `cp -r` backup). The `RetrievalBackend` SHALL be decoupled from embedding generation: `upsert` receives precomputed `IndexRecord.embedding` arrays from the caller-provided `EmbeddingProvider`, and `search` embeds the query via that provider then queries `vec_distance_cosine`.

#### Scenario: Upsert and search
- **WHEN** 10 `IndexRecord`s with 384-d embeddings are upserted into `SqliteVecBackend` and a query is embedded via `ONNXEmbeddingProvider`
- **THEN** `search(SearchRequest(query="...", top_k=3))` returns up to 3 `SearchHit`s ranked by cosine similarity with `dense_score` populated

#### Scenario: Space isolation
- **WHEN** two backends are created for different `space_id`s (`text.onnx.Xenova-all-MiniLM-L6-v2.v1` vs another model)
- **THEN** their `vec` tables and `IndexManifest`s are isolated and vectors from one space never appear in the other's search

### Requirement: Vector backend pluggability preserved
`QdrantBackend` (`qdrant-client`) and `LanceBackend` (`pylancedb`) SHALL remain available as `RetrievalBackend` implementations behind the same `VectorBackend` interface; callers SHALL NOT import `qdrant_client` or `lancedb` outside `index/` and `storage/`. Selecting `vector_backend="qdrant"` or `"lancedb"` SHALL route dense operations there while FTS5 and SQLite metadata remain unchanged.

#### Scenario: Qdrant opt-in still works
- **WHEN** `vector_backend="qdrant"` is configured and Qdrant is reachable
- **THEN** dense embeddings route to Qdrant while lexical search still uses FTS5, with no change to `Workspace.search` callers

## REMOVED Requirements

### Requirement: Txtai ANN retrieval
The `TxtaiBackend` (`txtai.embeddings.Embeddings` hybrid/sparse ANN) is removed. No scenario references `txtai` after this change.
