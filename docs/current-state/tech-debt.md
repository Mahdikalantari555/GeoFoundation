# Tech Debt & Code Health — Current State

Audit of `main` @ `364b897`. Findings verified against source; severity is pragmatic, not dogmatic.

## 1. Dead / vestigial code

| Item | Location | Evidence | Action candidate |
|---|---|---|---|
| Legacy Streamlit app | `apps/app.py` | Superseded by `apps/dashboard/`; README points to dashboard only | Delete or archive |
| `EventBus` subscribers unused | `core/events.py` | Workspace emits `asset.created`; nothing subscribes internally; no external API exposes subscriptions | Keep as extension point **or** wire logging/metrics; document decision |
| `EmbedderRegistry` / `BackendRegistry` | `core/plugin_registry.py` | Only `LoaderRegistry`/`ChunkerRegistry` are populated in practice | Wire or remove |
| Placeholder vision embedder | `embeddings/vision_embedder.py` `PlaceholderVisionEmbedder` | Stub returning synthetic vectors | Replace with real path via `LlamaCppVisionEmbedder` |
| Spike script + marker | `scripts/spike_txtai_embedding.py`, pytest marker `spike` | Served its validation purpose | Archive under benchmarks/ |

## 2. Duplicate functionality

| Duplication | Locations | Risk |
|---|---|---|
| **Two RRF implementations** | `retrieval/fusion.py:rrf_fuse()` vs private `_rrf_fuse()` in `core/workspace.py:1113` | Divergent fusion behavior between facade path and service path — highest-priority cleanup |
| Two search orchestrations | `Workspace.search/_fts_search/_dense_search/_numpy_dense_search` vs `retrieval/search_service.SearchService` (+ `_WorkspaceSearchAdapter` bridging) | Logic drift; hard to evolve filters once |
| Thin double wrappers | `services/search_service.py`, `services/chat_service.py` re-wrap retrieval/qa services that facade already delegates to | Extra indirection with no added behavior |
| Two UIs | `apps/app.py` vs `apps/dashboard/` | Confusion about canonical entry |

## 3. Missing tests (direct coverage)

Verified by import-scan across `tests/`:

| Module | Direct tests | Indirect coverage |
|---|---|---|
| `core/events.py` | none | emit-only paths exercised incidentally |
| `core/plugin_registry.py` | none | via loaders/chunkers usage |
| `retrieval/query_parser.py` | none | exercised through search integration tests |
| `retrieval/deduplicator.py` | none (only fusion tested) | partial via search tests |
| `ingest/job_queue.py` | none dedicated | partial via services tests |
| `qa/prompts.py` | none | snapshot-less prompt drift risk |
| `feedback/exporters/dataset_card.py` | none | export flow tested at higher level |
| `rs/raster/*` edge cases (nodata, CRS mismatch) | partial (`test_raster`) | golden fixtures only cover NDVI |

Also: no property-based tests anywhere; no benchmark regression gate in CI (no CI at all).

## 4. Missing documentation

- No `docs/` tree existed prior to this audit (only README + `.agent/spec` design docs).
- No CHANGELOG.md; version bumped ad hoc.
- Public Python API has docstrings but no generated reference (no mkdocs/sphinx).
- No contributor guide beyond README dev section.
- `.agent/spec/docs/*.md` describe *intended* design; they have drifted from implementation in places (e.g., spec mentions DOCX ingestion; code lacks a loader).

## 5. Structural smells

- `core/workspace.py` = 1152 LOC doing orchestration, SQL access, chunking dispatch, RRF, job fabrication. Facade is convenient but over-loaded; extraction into services would shrink it.
- Raw SQL strings inline in workspace.py alongside repositories — two persistence styles coexist.
- `_detect_mime` extension-table based; content sniffing absent → mis-typed files ingest silently as text.
- `services/ingestion_service.py` returns pending jobs but nothing runs them asynchronously — async story half-built.

## 6. Dependency/config debt

- `python-docx` declared in `[docs]` extra but no DOCX loader implemented (spec/README imply support).
- No CI pipeline (GitHub Actions etc.) enforcing ruff/mypy/pytest/coverage despite tooling config being complete.
- Coverage fail-under 80 configured but unverifiable without CI.
- Model defaults (`nomic-embed-text-v2-moe`, `olmoearth-nano`, `minicpm`) are string ids inside code; resolution depends on workspace settings correctness — no schema validation of model file existence until load time (doctor partially covers).

## 7. Security posture (local-first)

- SQL injection: low risk — parameterized queries throughout.
- Path traversal: object store keys are hex hashes; loaders read user-supplied paths by design (CLI trust model).
- Pickle/deserialization: vector backends use numpy save formats, not pickle — good.
- Main exposure: GGUF model files and ingested files are trusted-input assumptions; fine for single-user local use, would need revisiting for any server deployment.

## Recommended cleanup order

1. Kill duplicate RRF + unify search orchestration behind `SearchService`.
2. Add CI running ruff+mypy+pytest+coverage.
3. Delete legacy app + spike; decide EventBus fate.
4. Unit tests for query_parser, deduplicator, job_queue, prompts.
5. Extract SQL from workspace.py into repos; split facade.
