## 1. Cut torch/txtai from dependency graph

- [ ] 1.1 Edit `libs/geomemory/pyproject.toml`: remove `[project.optional-dependencies].ai` (`txtai`, `llama-cpp-python` stays only if already isolated), delete `[st]` (`sentence-transformers`, `huggingface-hub` stays via `onnx`), remove `torch`/`torchvision`/`torchaudio`/`accelerate`/`safetensors` from any required/extra; add lightweight base deps `onnxruntime>=1.18`, `tokenizers>=0.15`, `sqlite-vec>=0.1.6`, `huggingface-hub>=0.23` (either base or canonical `[onnx]`/`[sqlite-vec]` — decide and document; keep `vision` extra as sole torch holder). Verify `pip install -e libs/geomemory` → `pipdeptree | grep -E "torch|txtai"` empty.
- [ ] 1.2 Delete `src/geomemory/embeddings/sentence_transformer.py` and `src/geomemory/index/txtai_backend.py`; search/replace any remaining `import txtai` / `sentence_transformers` references (grep gate). Remove `ai`/`st` entry points from README/docs.
- [ ] 1.3 Add CI guard `scripts/check_no_torch_dep.py` and GitHub action step `pip install geomemory && python scripts/check_no_torch_dep.py && pipdeptree` failing if `torch`/`txtai` appear.

## 2. Promote ONNX provider + abstract EmbeddingProvider

- [ ] 2.1 Create `src/geomemory/embeddings/provider.py` (`EmbeddingProvider` Protocol: `space_id`, `model_id`, `dimension=384`, `embed`, `embed_query`, `embed_batch`; `ONNXEmbeddingProvider` wrapping `onnx_text.OnnxTextEmbedder` quantized path `Xenova/all-MiniLM-L6-v2` `onnx/model_quantized.onnx`, mean-pool, L2, e5 prefixes; stubs `OpenAIEmbeddingProvider`/`VoyageEmbeddingProvider`/`CustomEmbeddingProvider` raising `NotImplementedError` with actionable hint).
- [ ] 2.2 Retarget `src/geomemory/embeddings/factory.py:build_text_embedder` → returns `EmbeddingProvider`; keep `TextEmbedder` as deprecated alias for one minor (type alias to `EmbeddingProvider`) or delete after migration. Extend `WorkspaceSettings` (`core/models.py`): `embedding_provider ∈ {onnx, openai, voyage, custom, hashing, llamacpp}` (default `onnx`), `onnx_model_name: str = "Xenova/all-MiniLM-L6-v2"` (or `sentence-transformers/all-MiniLM-L6-v2` onnx-community mapping), `embedding_backend` deprecated alias.
- [ ] 2.3 Wire `OnnxTextEmbedder`/`ONNXEmbeddingProvider` to `embeddings/hub.py` (priority roots: `GEOMEMORY_EMBEDDING_ROOT` → `workspace.embedding_path` → `/mnt/data/LocalAI/Models/Embedding` → HF cache) and auto-download (`huggingface_hub.snapshot_download` onnx-community namespace) with `offline` guard (503 `embedding_unavailable`). Ensure `Xenova/all-MiniLM-L6-v2` is the documented primary quantized model.
- [ ] 2.4 Tests: `tests/embeddings/test_provider_interface.py`, `tests/embeddings/test_onnx_quantized.py` (384-d, quantized file preference), `tests/embeddings/test_onnx_parity.py` (cosine correlation >0.998 vs fixture), `tests/test_no_torch_dep.py`.

## 3. Replace txtai retrieval with sqlite-vec (+ pluggable Qdrant/LanceDB)

- [ ] 3.1 Implement `src/geomemory/index/sqlite_vec_backend.py:SqliteVecBackend` satisfying `RetrievalBackend` (`space_id=text.onnx.*.v1`, `upsert`, `delete`, `count`, `rebuild`, `search`) using `sqlite-vec` `vec0` table (`vec_segments` with `embedding[384] float`, cosine, id PK). Decouple from embedder — `upsert` receives precomputed `IndexRecord.embedding`. Handle extension load failure → `EmbeddingUnavailableError` with fallback hint; `from_database`/`rebuild` from `segment` table.
- [ ] 3.2 Update `src/geomemory/index/backend.py` + `src/geomemory/index/storage_backend.py` to declare `VectorBackend` pluggability; keep `src/geomemory/index/qdrant_backend.py` and `lance_backend.py` as optional `RetrievalBackend`s, `numpy_backend.py` as fallback. Ensure no caller imports `lancedb`/`qdrant_client` outside `index/` (abstraction hold).
- [ ] 3.3 Update `storage/schema.sql`: add `vec_segments` virtual table creation via `sqlite-vec` extension (guarded `CREATE VIRTUAL TABLE IF NOT EXISTS`), and migration from prior txtai indexes (no data copy — re-embed path). Keep FTS5 (`segments_fts`) triggers unchanged.
- [ ] 3.4 Update `services/index_service.py` and `retrieval/search_service.py` / `retrieval/fusion.py`: `build_index`/`rebuild_index` embed via `EmbeddingProvider`, upsert into `SqliteVecBackend`; `search` queries `SqliteVecBackend` for dense + FTS5 for sparse → `rrf_fuse`. Preserve `apply_hit_filters` (spatial/temporal/sensor) + `RetrievalRun` audit.
- [ ] 3.5 Update `services/doctor.py`: report `sqlite_vec: {installed, loadable, version}`, `embedding_provider: {active, space_id, dimension}`, remove `txtai` row.
- [ ] 3.6 Tests: `tests/index/test_sqlite_vec_backend.py` (upsert/delete/search isolation), `tests/retrieval/test_hybrid_sqlite_vec.py` (RRF with FTS5+vec), `tests/index/test_no_txtai_import.py`, `ruff`/`mypy --strict`.

## 4. Migration, CLI, and docs

- [ ] 4.1 Add `geomemory reindex` CLI (`cli/main.py` or `cli/reindex.py`): `geomemory reindex --workspace <path> [--collection <id>] [--provider onnx] [--model Xenova/all-MiniLM-L6-v2]` — scans `segment` rows, re-embeds via `EmbeddingProvider`, rebuilds `vec_segments`, writes fresh `IndexManifest` (`space_id`, `model_id`, `dimension=384`). Detect legacy `space_id=text.st.*` → warn `ReindexRequired`.
- [ ] 4.2 Write `docs/migration-txtai-to-onnx.md` (upgrade path: uninstall txtai/torch, `pip install geomemory[onnx,sqlite-vec]`, run `geomemory reindex`, verify `pipdeptree`, before/after image size).
- [ ] 4.3 Update `docs/current-state/*`, `ARCHITECTURE.md`, `README.md`, `openspec/specs/*` (archive `sentence-transformer-embeddings`), and gateway/server docs (`server/README.md`, Docker).
- [ ] 4.4 Benchmark: run `eval/retrieval` metrics on fixture corpus before/after; assert semantic quality parity (recall@k within 2 pp) and report startup/RSS/image size deltas in PR description. Mark all `tests/` green without `torch` installed.

## 5. Gateway + Docker follow-through (GeoFoundation root)

- [ ] 5.1 Update `server/pyproject.toml` / `requirements.txt` / `environment.yml` to no longer pull torch/txtai via geomemory extras; ensure `server/src/geofront_api` still imports only public facades (`geomemory`).
- [ ] 5.2 Update `Dockerfile` / `docker-compose.yml`: base image installs `onnxruntime` + `sqlite-vec` (CPU), drops `torch`/`txtai` layers; assert image size reduced by ≥1.5 GB vs baseline (CI `docker images` gate).
- [ ] 5.3 Regenerate `apps/web` API client if `WorkspaceSettings` schema changed (`pnpm gen:api`), verify Doctor/Settings/Index pages show `embedding_provider` and `sqlite_vec` status (web change may be follow-up openspec).
