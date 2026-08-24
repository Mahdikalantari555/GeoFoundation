# GeoMemory Roadmap (proposed)

Built on [gap-analysis.md](gap-analysis.md) and `docs/current-state/`. Versions are capability milestones, not dates. Each item cites the gap it closes.

## v0.1 — Consolidation ("make what exists trustworthy")

Theme: pay down debt so every later change is cheaper.

1. ~~Unify retrieval path: delete `_rrf_fuse` in workspace.py, route facade through `SearchService` only.~~ **PARTIAL (done in dedupe-RRF commit)**: duplicate `_rrf_fuse` and `_hit_sensor` removed; facade and `SearchService` share `rrf_fuse`/`apply_hit_filters`/`hit_sensor`. Remaining: wrap facade FTS/dense retrieval as `RetrievalBackend` adapters so `Workspace.search` calls `SearchService` directly. *(tech-debt #2)*
2. Add CI (GitHub Actions): ruff + mypy --strict + pytest + coverage ≥80 gate. *(debt #2)*
3. Close direct-test gaps: query_parser, deduplicator, job_queue, prompts, events, plugin_registry. *(missing tests)*
4. Decide & execute: delete legacy `apps/app.py`; archive spike script; wire-or-remove EventBus subscribers; remove Embedder/Backend registries or use them. *(dead code)*
5. DOCX decision: implement docx loader **or** drop python-docx from extras and spec. *(feature #2 mismatch)*
6. Extract inline SQL from facade into repositories; split facade into composition of services. *(bottleneck)*
7. Docs: keep `/docs` tree current; add CHANGELOG + API reference generation.
8. SQLite busy-retry/backoff helper for multi-process use.

Exit criteria: CI green on all PRs; no duplicate fusion logic; coverage ≥80 enforced; docs match code.

## v0.2 — Multimodal & scale hardening

Theme: make the RS half production-grade.

1. Real vision pipeline: replace placeholder embedder; integrate OLMoEarth GGUF end-to-end (ingest → tile → embed → ImageIndex → dashboard page). *(feature #10)*
2. ANN backend implementing existing `RetrievalBackend` protocol (e.g., hnswlib/faiss) selected by size threshold; keep numpy fallback. *(scaling)*
3. Raster robustness: nodata masking, CRS re-projection guard, large-scene streaming tiling wired into default ingest. *(features #9)*
4. Batch/streaming embedding for rebuilds (bounded RAM). *(scaling risk)*
5. RetrievalRun retention policy + object-store GC command (`geomemory vacuum`). *(unbounded growth)*
6. Golden tests for EVI + spectral edge cases; raster integration fixtures. *(missing tests)*
7. Persian groundwork: unicode61 FTS config for fa, query parser locale hook. *(multilingual)*

Exit criteria: image search demo works offline from raw GeoTIFF to cited answer; 100k-segment search < 100ms p95 with ANN backend.

## v0.3 — Agent interface & async execution

Theme: let other programs (agents) use the memory safely.

1. Optional server layer: FastAPI app exposing facade operations (ingest/search/ask/feedback) — same Pydantic models over HTTP; local-only bind by default. *(agent interface)*
2. MCP server exposing search/ask tools for coding agents. *(agent interface)*
3. Background worker consuming the `job` table (single worker process; checkpoint/resume already modeled). *(async gap)*
4. Streaming answers (SSE) from ask endpoint with citation events.
5. Model manager: download/verify GGUFs, detect stale embedding spaces by checksum, guided rebuild. *(model lifecycle)*
6. Auth-lite story: token file for local HTTP; document threat model before any network exposure.

Exit criteria: an external agent completes "ingest folder → ask → get cited answer" purely via API/MCP without importing Python.

## v1.0 — Stability contract

Theme: promise something and keep it.

1. SemVer + deprecation policy; public API frozen to documented surface; `py.typed` verified in release.
2. Docs site (mkdocs): tutorials / how-to / reference / explanation from `/docs`.
3. Benchmark baselines published (retrieval metrics on fixed fixtures) + regression gate in CI. *(eval exists → enforce)*
4. Packaging: wheels for py3.10–3.12; extras validated in isolated CI jobs.
5. Multilingual QA: fa prompts + fa abstention heuristics shipped behind settings. *(language parity)*
6. Plugin story finalized: external loader/embedder registration via entry points using existing registries. *(plugin_registry payoff)*
7. Migration tooling: `geomemory migrate` applying versioned schema upgrades with dry-run.

Exit criteria: downstream users upgrade across minor versions without code changes; quality regressions caught automatically.

## Explicitly out of scope until demand exists

- Multi-tenant/cloud deployment, distributed ingestion, GPU scheduling service.
- Learned rerankers requiring training runs.
- Geometry-level spatial queries beyond bbox (postgis-class features).
