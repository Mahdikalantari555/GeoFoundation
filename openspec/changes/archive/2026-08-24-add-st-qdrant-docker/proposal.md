# Proposal: add-st-qdrant-docker

## Why

GeoMemory's dense retrieval currently supports only offline hashing embeddings and llama-cpp GGUF models, and its only vector index is a flat on-disk numpy store — adequate for prototypes, but weak on semantic quality (hashing) and scale/recall (flat scan). Research workloads also need reproducible, one-command environments. Adding sentence-transformers embeddings (multilingual e5), a production-grade Qdrant vector backend, and Docker packaging makes GeoMemory usable for real multilingual (en/fa) remote-sensing corpora at meaningful scale.

## What Changes

- New `SentenceTransformerEmbedder` implementing the existing `TextEmbedder` protocol (`space_id`, `model_id`, `embed`, `embed_batch`); lazy import so core package stays torch-free; **default model `sentence-transformers/all-MiniLM-L6-v2`** (lightweight ~90MB, low memory, fast download); `multilingual-e5-base` and `BAAI/bge-m3` supported as opt-in alternatives via `st_model_name`; input prefixing applied only for model families that require it (e5 `query: `/`passage: `), passthrough otherwise.
- New `QdrantBackend` implementing the existing `RetrievalBackend` protocol (`upsert/search/delete/rebuild/count` + `save/load/exists` compatibility); one Qdrant collection per embedding space (`space_id` as collection name) preserving the space-isolation invariant; lazy import of `qdrant-client`.
- Backend/embedder selection seam: `WorkspaceSettings` gains `embedding_backend`, `st_model_name`, `vector_backend`, `qdrant_url`, `qdrant_api_key`; `IndexService._embedder()` and dense build path select from settings instead of hardcoding `VectorBackend`.
- Embedding-model lifecycle safety: build manifests record the embedding model (name, dimension, space id); search detects a query-embedder vs index model mismatch and warns before returning results; changing the embedding model requires full reindexing (space isolation already guarantees old indexes are never reused). Single-model-per-project by default; multi-index architectures remain a future option.
- Optional dependency extras `[st]` (sentence-transformers) and `[vector]` (qdrant-client) in `pyproject.toml`; `geomemory doctor` reports both.
- Docker packaging: multi-stage `Dockerfile` (CLI target + Streamlit UI target) and `docker-compose.yml` wiring `qdrant` service + geomemory app with volumes for workspace data and HF model cache.

## Capabilities

### New Capabilities
- `sentence-transformer-embeddings`: text embedding via sentence-transformers/e5 models behind the `TextEmbedder` protocol, with e5 prefix handling and space isolation.
- `qdrant-vector-backend`: server-mode Qdrant retrieval backend behind the `RetrievalBackend` protocol, selected by workspace config, collection-per-space.
- `docker-deployment`: reproducible container images (CLI + Streamlit) and compose stack including Qdrant.

### Modified Capabilities

(none — first OpenSpec change in this repo; no baseline specs exist yet)

## Impact

- **Code**: `src/geomemory/embeddings/` (+1 module), `src/geomemory/index/` (+1 module), `src/geomemory/core/models.py` (`WorkspaceSettings` fields), `src/geomemory/services/index_service.py` (embedder/backend selection, manifest metadata), `src/geomemory/retrieval/search_service.py` (mismatch warning hook), `src/geomemory/services/doctor.py` (optional-deps list).
- **APIs**: no breaking changes to public API; new settings keys are additive with safe defaults (existing behavior unchanged when new keys absent).
- **Dependencies**: optional extras only — `sentence-transformers>=3.0`, `qdrant-client>=1.10`; core install remains torch-free.
- **Systems**: Qdrant runs as external service (compose or user-provided URL); model download requires network on first use unless cache volume mounted (conflicts with `offline=True` default are surfaced by doctor, not silently ignored).
