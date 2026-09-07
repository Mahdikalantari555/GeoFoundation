## Purpose
Keep ingestion feature parity while swapping the indexing backend from txtai ANN to sqlite-vec via EmbeddingProvider.

## MODIFIED Requirements

### Requirement: Build and update index from ingested segments
When segments are ingested (documents, code, etc.), the system SHALL embed them via the configured `EmbeddingProvider` (default `ONNXEmbeddingProvider` `Xenova/all-MiniLM-L6-v2`, 384-d, quantized) and upsert the resulting vectors into the configured `RetrievalBackend` (default `SqliteVecBackend`). The ingest pipeline SHALL NOT call `txtai` or `sentence-transformers`; chunking, metadata storage, and provenance (`answer → citation → segment → asset_revision → objects/<sha256>`) remain unchanged.

#### Scenario: Ingest indexes via sqlite-vec
- **WHEN** a document with 3 segments is ingested into a fresh workspace
- **THEN** `segment` rows are inserted, 3 vectors of dimension 384 are upserted into `vec_segments`, and `IndexManifest` records `space_id=text.onnx.Xenova-all-MiniLM-L6-v2.v1` with `dimension=384`

#### Scenario: Rebuild after provider switch
- **WHEN** `rebuild_index` is invoked after switching `embedding_provider` or `onnx_model_name`
- **THEN** all vectors in the target space are re-embedded via the new provider and no stale vectors from the old space remain
