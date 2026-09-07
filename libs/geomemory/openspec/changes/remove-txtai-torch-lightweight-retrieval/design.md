## Context

Current `geomemory` ships a txtai-based retrieval backend (`index/txtai_backend.py` → `txtai.embeddings.Embeddings(content=True, hybrid=True, sparse=True)`) and an optional `SentenceTransformerEmbedder` (`sentence-transformers` + `torch`) for dense text vectors. `pyproject.toml` exposes `ai = [txtai>=8.0, llama-cpp-python]`, `st = [sentence-transformers, huggingface-hub]`, `onnx = [onnxruntime, tokenizers, huggingface-hub]`, and `vision = [torch, olmoearth-pretrain]`. The result: `pip install geomemory[ai]` or `[st]` pulls a CUDA-capable torch wheel (2–3 GB), slow import, and a hard ANN dependency via txtai's internal index.

Meanwhile `embeddings/onnx_text.py:OnnxTextEmbedder` already implements the full inference contract (tokenizer.json + model.onnx/onnx/model_quantized.onnx, CPUExecutionProvider, mean-pool + L2, e5 prefixes, space_id `text.onnx.<safe>.v1`) with lazy imports, and `embeddings/hub.py:EmbeddingModelHub` scans `/mnt/data/LocalAI/Models/Embedding`, `~/.cache/huggingface`, and workspace indexes for local models. `storage/schema.sql` already has FTS5 (`segments_fts` + triggers) and SQLite WAL/RTree. What is missing is (a) cutting the torch/txtai graph so the base install stays light, (b) a provider abstraction so callers do not branch on `sentence_transformers` vs `onnxruntime`, and (c) a dense backend that pairs naturally with SQLite (sqlite-vec) instead of txtai's opaque `Embeddings` DB.

Consumers: `GeoMemory` facade (`core/workspace.py`), `services/index_service.py`, `retrieval/search_service.py` (fusion), CLI (`cli/main.py`), and the gateway (`server/src/geofront_api` — which imports only public facades). Gateways/docker images currently include torch via the `ai` extra, inflating CI and container size.

## Goals / Non-Goals

**Goals:**
- `pip install geomemory` never installs `txtai` or `torch` (verified by `pipdeptree`).
- Dense text embeddings exclusively via `onnxruntime` + quantized `Xenova/all-MiniLM-L6-v2` (384-d) by default; parity with previous ST quality.
- Vector storage via `sqlite-vec` (preferred) — embedded, CPU, no server; Qdrant/LanceDB remain pluggable via `VectorBackend`.
- A stable `EmbeddingProvider` seam so future cloud providers (OpenAI, Voyage, Custom) slot in without forking callers.
- Feature parity (ingest/metadata/chunking/semantic/hybrid/RAG/geospatial), plus a `reindex` utility + migration docs.

**Non-Goals:**
- Vision ONNX migration (OLMoEarth Nano stays `torch` behind opt-in `[vision]`; base remains torch-free).
- Training/fine-tuning embeddings; changing the FTS5 schema or RRF constants.
- Forcing Qdrant/LanceDB as defaults (they stay optional; `sqlite-vec` is the lightweight default).
- Automatic in-place conversion of txtai ANN files (re-embed is the supported migration path).

## Decisions

- **Quantized ONNX model Xenova/all-MiniLM-L6-v2 via onnxruntime+tokenizers, not optimum/sentence-transformers[onnx]**: `optimum[onnxruntime]` chains transformers+torch exporters and inflates the image; `sentencetransformers[onnx]` still drags `torch` for fallback. Direct `onnxruntime.InferenceSession` + `tokenizers.Tokenizer.from_file(tokenizer.json)` gives the smallest transitive closure (numpy + onnxruntime + tokenizers). Rationale: keeps base deps <200 MB and CPU-only; already validated in `onnx_text.py` (prefer `onnx/model_quantized.onnx` → `onnx/model.onnx` → `model_quantized.onnx`). Alternate `ONNX via optimum` rejected for size/startup.
- **EmbeddingProvider protocol over TextEmbedder alias**: current `TextEmbedder` protocol (`space_id`, `model_id`, `embed`, `embed_batch`) is synchronous and modality-coupled. New `EmbeddingProvider` adds `dimension`, `embed_query`, provider-agnostic `model_id`, and an explicit `name` for diagnostics. `ONNXEmbeddingProvider` wraps `OnnxTextEmbedder` internals. Future `OpenAIProvider`/`VoyageProvider` implement the same shape but call HTTP (no `torch`/`onnxruntime`). Non-goal: keep `TextEmbedder` as deprecated alias for one minor to ease migration.
- **sqlite-vec as default dense backend, not Qdrant/LanceDB**: `sqlite-vec` ships as a Python extension (`sqlite-vec`) that adds a `vec0` virtual table inside the workspace `geomemory.db` (or sibling `.vec` file), so backup stays `cp -r workspace`. Qdrant requires a server (optional `vector` extra), LanceDB requires `pylancedb` + Arrow. Decision: `SqliteVecBackend(space_id, db_path, dimension=384)` with `vec_segments(vec embedding[384] float, id text primary key, metadata)`; search via `vec_distance_cosine`. Fallback chain: `sqlite-vec` → `NumpyBackend` (pure numpy TF) if extension unavailable → optional `QdrantBackend`/`LanceBackend` when configured. Abstraction: `RetrievalBackend` no longer embeds; callers pass precomputed `IndexRecord.embedding`.
- **Delete SentenceTransformerEmbedder + TxtaiBackend**: rather than deprecate behind a flag, remove the files and the `[st]`/`[ai]` extras that pull torch. Rationale: the dependency graph is the bug; keeping the code keeps the graph reachable via transitive pins and confuses newcomers. Archive the spec (`sentence-transformer-embeddings`) with a migration note pointing to `embedding-provider`.
- **Manifest-driven migration**: existing indexes carry `IndexManifest(space_id, model_id, dimension, checksum, created_at)`. On `Workspace.open`, compare manifest `space_id`/`model_id` vs current provider; mismatch → emit `ReindexRequired` warning (not silent reuse) and require `geomemory reindex` or `Workspace.rebuild_index`. No automatic re-embedding on open (preserves offline/data-sovereign guarantee; user opts into download/network).
- **Dependency hygiene — move onnx to base or keep [onnx] canonical**: evaluate during apply. Preferred: `onnxruntime`, `tokenizers`, `sqlite-vec`, `huggingface-hub` in base `[project.dependencies]` so default install works offline-after-first-download without extras. If image-size concern is valid for minimal installs, keep `[onnx]` as canonical and make `pyproject.toml` `[project.dependencies]` suggest `geomemory[onnx]` in docs/doctor, but gateway Docker bakes `onnx`. Decision deferred to apply; either way `torch` must not appear in base.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| ONNX parity drift vs previous ST vectors (recall drop) | Golden set: 50 fixture texts embedded via old ST vs new quantized ONNX; cosine correlation >0.998, mean L2 delta <1e-3 (carried from `embedding-model-management-onnx`). Benchmark `retrieval/metrics` before/after on shipped fixtures; gate CI. |
| sqlite-vec platform coverage (wheels for arm64/musl, Colab) | Pin `sqlite-vec>=0.1.6` with wheels for linux/amd64, macos/arm64. If extension fails to load at runtime, `SqliteVecBackend.__init__` raises `EmbeddingUnavailableError` with `hint="pip install geomemory[sqlite-vec]"` and `SearchService` falls back to `NumpyBackend` (keyword-only degradation, never crash). Server Doctor reports `sqlite_vec: {installed, loadable, version}`. |
| Existing txtai indexes become unreadable | Provide `geomemory reindex --workspace <path> [--collection <id>]` that reads `segment` rows, re-embeds via `EmbeddingProvider`, upserts into `vec_segments`, and writes fresh `IndexManifest`. Docs `docs/migration-txtai-to-onnx.md` with before/after `pipdeptree` and size numbers. No in-place ANN conversion attempted. |
| Vision still needs torch (OLMoEarth) → contradicts "remove torch completely" | Isolate `torch` to opt-in `[vision]` only; base install + `pipdeptree` passes without torch. Document that `geomemory[vision]` re-introduces torch intentionally; no other path pulls it. |
| EmbeddingProvider stubs (OpenAI/Voyage) tempt premature network code | Stubs raise `NotImplementedError` with `hint="configure llm_api_key_env / voyage_api_key"`; no HTTP client added in this change. Interface only. |
| Startup still needs model download (Xenova) | `EmbeddingModelHub.download` with progress callback + background job for gateway (`POST /api/v1/models/download` already exists); offline guard returns `503 embedding_unavailable` with hint. |

## Verification

- **Unit — dependency graph**: `scripts/check_no_torch_dep.py` (or inline `python -c "import importlib.metadata; assert 'torch' not in ...; assert 'txtai' not in ..."`) runs in CI after `pip install geomemory` in a clean venv; also `pipdeptree` grep gate.
- **Unit — provider**: `tests/embeddings/test_provider_interface.py` (protocol shape), `tests/embeddings/test_onnx_quantized.py` (mean-pool/L2/384-d, quantized path), `tests/embeddings/test_onnx_parity.py` (correlation >0.998).
- **Unit — backends**: `tests/index/test_sqlite_vec_backend.py` (upsert/delete/count/search, 384-d, isolated spaces), `tests/index/test_no_txtai_import.py` (assert `index.txtai_backend` missing), `tests/retrieval/test_hybrid_sqlite_vec.py` (FTS5 + vec RRF fused).
- **Integration — migration**: `tests/test_reindex_migration.py` (create legacy-ish workspace with `NumpyBackend` segments, `reindex` via ONNX stub, assert search returns same ids with updated manifest).
- **Integration — gateway/server**: `server/tests/test_no_torch_dep.py` not needed (gateway imports public facade only — facade no longer pulls txtai). Existing `server/tests` pass with `GEOMEMORY_EMBEDDING_ROOT=/tmp`.
- **Lint/type**: `conda run -n geospatial ruff check libs/geomemory/src` and `mypy --strict libs/geomemory/src` (new provider/backend typed).
- **Manual — size**: `docker build -f Dockerfile . && docker images | grep geomemory` before/after; `du -sh $(python -c 'import geomemory; print(geomemory.__path__)')`; startup `time python -c "import geomemory; w=geomemory.GeoMemory.create(...)"` faster than txtai baseline.
