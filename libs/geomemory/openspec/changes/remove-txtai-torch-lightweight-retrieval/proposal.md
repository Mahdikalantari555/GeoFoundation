# Proposal: remove-txtai-torch-lightweight-retrieval

## Why

GeoMemory's current retrieval stack depends on **txtai** (which transitively pulls `torch`, `sentence-transformers`, `transformers`, `accelerate`, `safetensors`) for embedding + ANN. This makes the default install multi-GB, slow to provision in CI/Docker, and undeployable on Colab/serverless/low-RAM hosts. The capability is retrieval-focused (FTS5 + dense cosine + RRF fusion) and does not need a PyTorch runtime. The ONNX path (`onnx_text.py` + `onnxruntime` + `tokenizers`) already delivers 384-d `all-MiniLM-L6-v2` embeddings via `model_quantized.onnx` with mean-pool + L2 norm, and `sqlite-vec` provides an embedded vector extension for SQLite without a server.

Keeping txtai blocks the project's **local-first, CPU-only, lightweight** promise, inflates `pip install geomemory[ai]` to require CUDA-capable wheels, and couples vector storage to an opaque `Embeddings` database. A refactor must cut the graph so `pip install geomemory` never installs `txtai` or `torch`, while preserving feature parity for ingestion, metadata, chunking, semantic/hybrid search, RAG, and geospatial filtering.

## What Changes

### 1. Remove txtai completely
- Delete `index/txtai_backend.py`, `sentence_transformer.py` bridge that txtai relied on, and all `geomemory[ai]` / `geomemory[st]` extras that pull txtai/torch.
- No code path imports `txtai.*`; `RetrievalBackend` no longer has a txtai implementation; `TxtaiBackend` deleted.
- CLI `geomemory` and gateway never reference txtai; docs/ARCHITECTURE note updated.

### 2. Remove PyTorch-based inference from the default graph
- `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `transformers` (except optional tokenizer-only), `accelerate`, `safetensors` removed from required and recommended runtime deps.
- `torch` remains only behind an **opt-in** `geomemory[vision]` extra (OLMoEarth Nano) — default install stays torch-free; `SentenceTransformerEmbedder` deleted, its behavior superseded by ONNX.
- Verification: `pip install geomemory` + `pipdeptree | grep -i torch` yields no matches; CI enforces the check.

### 3. ONNX Runtime as the canonical embedding engine
- `OnnxTextEmbedder` becomes the **default** `TextEmbedder` (space `text.onnx.<safe-model>.v1`, 384-d).
- Uses `onnxruntime` + `tokenizers` + quantized weights `Xenova/all-MiniLM-L6-v2` (`onnx/model_quantized.onnx` preferred, fallback `onnx/model.onnx` / `model_quantized.onnx`).
- Mean-pool over `attention_mask`, L2-normalize, e5 prefix handling preserved.
- Existing `embeddings/hub.py` (scan `/mnt/data/LocalAI/Models/Embedding` → HF cache) and auto-download (`huggingface-hub` → `onnx-community/all-MiniLM-L6-v2-ONNX`) retained; `SentenceTransformerEmbedder` path removed.

### 4. Dedicated EmbeddingProvider interface
- New protocol `EmbeddingProvider` (in `embeddings/provider.py`) abstracts `embed(texts) -> np.ndarray`, `embed_query`, `embed_batch`, `space_id`, `model_id`, `dimension`.
- Implementations: `ONNXEmbeddingProvider` (canonical), `FutureOpenAIProvider`, `FutureVoyageProvider`, `FutureCustomProvider` stubs behind the protocol — `GeoMemory`, `SearchService`, `IndexService`, and `RetrievalBackend` depend only on the interface.
- `TextEmbedder` protocol retained as legacy alias or removed after migration; factory `embeddings/factory.py:build_text_embedder` returns `EmbeddingProvider`.

### 5. Replace txtai retrieval with SQLite-native stack
- Lexical: existing `SQLite FTS5` (`segments_fts` + triggers) unchanged.
- Dense: new `SqliteVecBackend` (`index/sqlite_vec_backend.py`) using `sqlite-vec` virtual table `vec_segments` (cosine, 384-d), with `sqlite-vec` as **preferred** dense store.
- Pluggable: `QdrantBackend` and `LanceBackend` (LanceDB) remain as `RetrievalBackend` alternatives via `VectorBackend` abstraction; `NumpyBackend` stays as pure-numpy fallback.
- `VectorBackend`/`RetrievalBackend` interface decoupled from embedding generation — vector store never calls embedder internally.
- Hybrid: `retrieval/fusion.rrf_fuse` + `SearchService` unchanged; dense scores now from `sqlite-vec` cosine, fused with FTS5 BM25.

### 6. Preserve feature parity
- Document ingestion, metadata storage, chunking, semantic search, hybrid search, similarity retrieval, RAG workflows, geospatial (bbox/RTree/temporal/sensor) filters remain unchanged externally; `Workspace.search`, `Workspace.ask`, `ingest`, `rebuild_index` signatures preserved.

### 7. Dependency hygiene
- Lightweight runtime: `numpy`, `onnxruntime`, `tokenizers`, `sqlite-vec`, `pydantic`, `pandas`, `geopandas`, `shapely`, `pyarrow`, `huggingface-hub`, `PyYAML`, `click`.
- Deleted from graph: `txtai`, `torch*`, `sentence-transformers`, `accelerate`, `safetensors` (unless re-introduced transitively by an opt-in extra).
- `pyproject.toml` `[project.dependencies]` minimal; `[onnx]`, `[vector]`, `[lancedb]`, `[vision]` remain opt-in; new `[sqlite-vec]` or fold into base.

### 8. Performance + backward compat
- Faster startup (no torch import), lower RSS (ONNX CPU), smaller wheel/Docker (-2–3 GB).
- Migration: `geomemory reindex --from txtai --to sqlite-vec` utility, docs `docs/migration-txtai-to-onnx.md`, and manifest-based detection (`IndexManifest.space_id` mismatch triggers `ReindexRequired` warning).
- Success gate: all tests pass with no `torch` installed; `pip install geomemory` never pulls `torch`/`txtai` (CI `pipdeptree` assert).

## Capabilities

### New Capabilities
- `embedding-provider`: Provider abstraction (`ONNXEmbeddingProvider` canonical, stubs for OpenAI/Voyage/Custom) decoupling consumers from inference details.

### Modified Capabilities
- `search-retrieval`: retrieval without txtai — FTS5 + sqlite-vec (+ Qdrant/LanceDB pluggable), RRF fusion preserved.
- `storage-architecture`: vector storage defaults to `sqlite-vec` embedded; LanceDB/Qdrant remain pluggable; no mandatory external service.
- `ingestion`: `rebuild_index`/`ingest` emit `sqlite-vec` embeddings via `EmbeddingProvider` instead of txtai ANN.
- `sentence-transformer-embeddings`: retired — its contract superseded by `embedding-provider`/`onnx` (spec archived).
- `workspace-management`: settings field `embedding_backend` deprecates `sentence-transformers`; adds `embedding_provider ∈ {onnx, openai, voyage, custom, hashing, llamacpp}` with `onnx_model_name` default `Xenova/all-MiniLM-L6-v2`.
- `docker-deployment`: base image drops torch/txtai layers, adds `onnxruntime` + `sqlite-vec`; size regression gate.

### Removed Capabilities (archived)
- `txtai` retrieval backend and sentence-transformers torch inference from default distribution.

## Impact

- **Code**: `embeddings/provider.py` (new), `embeddings/onnx_text.py` (promoted to canonical), `embeddings/sentence_transformer.py` (deleted), `embeddings/factory.py` (retarget), `index/txtai_backend.py` (deleted), `index/sqlite_vec_backend.py` (new), `index/backend.py` (VectorBackend decoupling), `services/index_service.py`, `core/models.py` (`WorkspaceSettings`), `core/workspace.py`, `storage/schema.sql` (vec table), `cli/*` reindex command, `pyproject.toml` deps, Dockerfiles, docs/migration.
- **APIs**: Public facade `GeoMemory` unchanged externally; `space_id` values change from `text.st.*` to `text.onnx.*` — clients with cached indexes must reindex (migration warning, not silent).
- **Dependencies**: Base install shrinks multi-GB; `[ai]` extra removed; `[st]` removed; new `[onnx]` canonical (or moved to base). CI adds `pipdeptree` guard.
- **Risks**: ONNX parity vs previous ST vectors (guard: golden cosine correlation >0.998 on 50-fixture set, already in `embedding-model-management-onnx` decision); `sqlite-vec` availability on all platforms (fallback to `NumpyBackend` + optional Qdrant/LanceDB); txtai index migration requires re-embed (one-time cost, documented).
- **Tests**: `tests/embeddings/*` (ONNX quantized parity, provider interface), `tests/index/test_sqlite_vec_backend.py`, `tests/test_no_torch_dep.py` (assert no txtai/torch import), migration integration `tests/test_reindex_migration.py`.
