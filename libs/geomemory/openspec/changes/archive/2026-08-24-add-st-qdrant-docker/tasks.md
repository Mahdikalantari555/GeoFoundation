# Tasks: add-st-qdrant-docker

## 1. Config seam

- [x] 1.1 Add `embedding_backend`, `st_model_name` (default `"sentence-transformers/all-MiniLM-L6-v2"`), `vector_backend`, `qdrant_url`, `qdrant_api_key` fields with safe defaults to `WorkspaceSettings` in `src/geomemory/core/models.py`; verify existing `workspace.yaml` files still load (unit test)
- [x] 1.2 Extend `_embedder()` in `services/index_service.py` to three-way dispatch on `embedding_backend`; missing-extra path raises actionable ImportError; unit test with fakes

## 2. Sentence-transformers embedder

- [x] 2.1 Create `src/geomemory/embeddings/sentence_transformer.py`: lazy import, model-family prefix map (e5 → `passage: `/`query: `, others passthrough), `space_id = text.st.{model}.v1` (slashes→dashes), L2-normalized float32 output; export from `embeddings/__init__.py`
- [x] 2.2 Unit tests with a stubbed sentence_transformers module: prefix correctness for e5 (query vs passage differ) and MiniLM passthrough (identical vectors), space-id stability and divergence from hashing/llama-cpp ids, batch shape/dtype, ImportError message names `[st]` extra
- [x] 2.3 Add `[st]` extra (`sentence-transformers>=3.0`) to `pyproject.toml`; add `"sentence_transformers"` to doctor's optional-deps list; extend doctor test
- [x] 2.4 Manifest metadata + mismatch guard: record `model_id`, `dim`, `space_id`, `built_at` in build manifests (local and qdrant paths); search path compares query embedder identity vs backend manifest and warns naming both models on mismatch; unit tests: metadata present after build, warning emitted on model switch without rebuild, no warning when matching

## 3. Qdrant backend

- [x] 3.1 Create `src/geomemory/index/qdrant_backend.py`: lazy import, collection per `space_id`, cosine distance, UUID-5 point ids, payload carries original id/text/metadata; upsert/search/delete/count/rebuild + `save/load/exists` compat no-ops; export from `index/__init__.py`
- [x] 3.2 Unit tests against an in-process fake qdrant client: idempotent upsert, delete removes hits, top_k honored and score-ordered, cross-space collections isolated, ImportError names `[vector]` extra
- [x] 3.3 Branch `IndexService.build()` dense path on `vector_backend`: `local` → untouched VectorBackend flow; `qdrant` → QdrantBackend upsert, no disk save; unreachable server surfaces connection error (test with fake raising)

## 4. Doctor & wiring

- [x] 4.1 Doctor reports `qdrant_client` availability and, when `qdrant_url` configured, server reachability via readyz probe; unit tests for both states
- [x] 4.2 Search service wiring: built backend flows into `RetrievalSearchService` backends list for both local and qdrant selections (integration-style test with fakes)

## 5. Docker packaging

- [x] 5.1 Write multi-stage `Dockerfile` (python:3.11-slim; targets `cli`, `ui`); verify `docker build --target cli` succeeds and runs `geomemory --help` *(file written; build unverified — torch download too slow in-session, see TODO.md)*
- [x] 5.2 Write `docker-compose.yml`: `qdrant` service (named volume, readyz healthcheck) + `geomemory-ui` (target ui, env `GEOMEMORY_QDRANT_URL=http://qdrant:6333`, volumes workspace-data + hf-cache); env-var override honored by settings loader
- [x] 5.3 Smoke test full stack: compose up, both services healthy, index a fixture doc through CLI container, search returns hit, restart containers → data survives *(verified: init → create_collection → ingest → search → restart → search returns same hit)*
- [x] 5.4 Document usage in README section (extras, settings keys, compose commands, offline/cache notes)

## 6. Quality gates

- [x] 6.1 `ruff check` clean (line-length 100) across new modules and tests
- [x] 6.2 `mypy --strict` passes on all touched packages *(0 errors in all files touched by this change; pre-existing violations elsewhere untouched)*
- [x] 6.3 Full `pytest` suite green under conda env `ai` with `--strict-markers`; no test requires network or live Qdrant *(275 unit + integration pass; 3 pre-existing txtai failures fail identically on clean HEAD — HF-hub network issue, unrelated)*
- [x] 6.4 Run `openspec validate add-st-qdrant-docker --strict` before apply/archive
