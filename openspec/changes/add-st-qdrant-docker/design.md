# Design: add-st-qdrant-docker

## Context

Verified from code (this session):

- `TextEmbedder` protocol (`src/geomemory/embeddings/text_embedder.py`): `space_id`, `model_id`, `embed(Sequence[str]) -> (N, D) float32`, `embed_batch(texts, batch_size)`. Existing impls: `HashingTextEmbedder`, `LlamaCppTextEmbedder`.
- `RetrievalBackend` protocol (`src/geomemory/index/backend.py`): `space_id`, `upsert(list[IndexRecord])`, `search(SearchRequest) -> list[SearchHit]`, `delete(ids)`, `rebuild(manifest)`, `count()`. `IndexRecord` carries optional `embedding`; `SearchRequest` carries `query_embedding`.
- Lazy-import pattern established by `TxtaiBackend.__init__` (ImportError with "install extra" message).
- **Hardcode #1**: `services/index_service.py::_embedder()` — `if model_path: LlamaCpp else Hashing`.
- **Hardcode #2**: `services/index_service.py::build()` — always constructs/persists `VectorBackend` under `index_dir/<space_id>`, branching on `VectorBackend.exists(dir)` / `load()` / `save()`.
- `RetrievalSearchService(retrieval/search_service.py).__init__(backends: list[Any])` — already accepts any duck-typed backend; no changes needed there.
- `WorkspaceSettings` (`core/models.py`): pydantic model persisted to `workspace.yaml`; has `offline=True`, `embedding_path`, `batch_size`. No embedder/backend selector fields yet.
- `services/doctor.py::check_optional_deps()` — static module-name tuple; add entries.
- No Docker files exist anywhere in the repo.
- Project rules: strict mypy, ruff (line 100), pytest strict markers, conda env `ai` for all runs.

## Goals / Non-Goals

**Goals:**
- ST + Qdrant as pure additions behind existing protocols; zero behavior change when unset.
- One selection seam in config consumed by IndexService.
- e5 prefix handling invisible to callers.
- Compose stack reproducible on a clean machine.

**Non-Goals:**
- Migrating existing local indexes to Qdrant (rebuild instead).
- Sparse/hybrid search via Qdrant (dense-only backend; hybrid fusion stays in retrieval layer).
- GPU/torch tuning, quantization, or ONNX export.
- CI running live Qdrant or downloading models — unit tests use fakes/stubs.
- Multi-node Qdrant, auth beyond a static API key.

## Decisions

### D1 — Embedder selection via settings field
Add `embedding_backend: Literal["hashing", "llama-cpp", "sentence-transformers"] = "hashing"` and `st_model_name: str = "intfloat/multilingual-e5-small"` to `WorkspaceSettings`. `_embedder()` becomes a three-way dispatch. Alternative considered: auto-detect installed extras — rejected (surprising, untestable ordering).

### D2 — space_id derivation
`sentence-transformers` embedders report `space_id = f"text.st.{model_name}.v1"` (slashes → `-`). Guarantees per-model space isolation and stable rebuild detection. Hashing keeps `text.hash.v1`.

### D3 — e5 prefixes inside the embedder
`SentenceTransformerEmbedder.embed()` prefixes every input with `"passage: "`; a dedicated `embed_query(texts)` method uses `"query: "`. Search path calls `embed_query`; ingest path calls `embed`. Rationale: e5 models degrade silently without prefixes; callers must not know. Non-e5 models get empty-prefix passthrough (prefix map keyed by model family).

### D4 — QdrantBackend maps contract to collections
Collection name = `space_id`; vector params created on first upsert with dimension from first vector and cosine distance. Point id = deterministic UUID-5 of record id (Qdrant rejects arbitrary string ids). Payload stores `text`, `metadata`, original record id. `save()/load()/exists()` become compatibility no-ops/flags so `IndexService` can treat backends uniformly; real persistence is server-side. Alternative: qdrant local mode — rejected (defeats the point of a server-grade store; compose runs the server).

### D5 — Backend selection seam in IndexService.build()
Settings field `vector_backend: Literal["local", "qdrant"] = "local"`, plus `qdrant_url: str | None`, `qdrant_api_key: str | None`. Build branches once: `local` → existing `VectorBackend` path untouched; `qdrant` → construct `QdrantBackend(url, collection=space_id)` and upsert; skip disk save. Search service receives whichever backend was built — it already consumes any protocol implementation.

### D6 — Optional extras, lazy imports everywhere
`[st]`: `sentence-transformers>=3.0`. `[vector]`: `qdrant-client>=1.10`. Both modules imported inside constructors only (TxtaiBackend pattern). Core install stays torch-free.

### D7 — Docker: multi-stage single Dockerfile
Base `python:3.11-slim`; system deps for rasterio/geopandas wheels; targets:
- `cli`: installs `.[ai,st,vector,docs,rs]`, entrypoint `geomemory`
- `ui`: FROM cli, installs streamlit, runs `streamlit run apps/app.py`
`docker-compose.yml`: services `qdrant` (official image, volume `qdrant_storage`, healthcheck on `:6333/readyz`) and `geomemory-ui` (build target ui, env `GEOMEMORY_QDRANT_URL=http://qdrant:6333`, volumes `workspace_data` + `hf_cache`). Env vars override settings so container config needs no file edits.

## Risks / Trade-offs

- **Model download at first use vs `offline=True` default**: doctor reports both facts; docs state HF cache volume requirement. Not silently resolved.
- **Flat numpy scan outperforms Qdrant for tiny corpora**: accepted — Qdrant is opt-in; local remains default.
- **UUID-5 point ids lose direct string lookup**: payload keeps the original id; delete-by-id resolves through UUID-5 deterministically.
- **Streamlit app in-container must use public API only** (project invariant): UI target gets config purely via env/settings, no internal imports introduced.
- **torch wheel size (~2GB)** bloats images: accepted for alpha; slim base + wheel-only install documented.
