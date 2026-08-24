# Gap Analysis — Current Implementation vs Project Goals

Baseline goals from `.agent/spec/project-spec.json` (5 objectives, 15 features) compared against verified implementation state (`docs/current-state/`).

Legend: ✅ done · 🟡 partial · ❌ missing

## 1. Feature-by-feature

| # | Spec feature | State | Evidence / gap |
|---|---|---|---|
| 1 | Workspace Management | ✅ | init/open/settings/collections/doctor |
| 2 | Document Ingestion | 🟡 | PDF/text/code/GeoTIFF/GeoJSON loaders exist; **DOCX declared in deps but no loader**; no HTML/markdown-aware loader |
| 3 | Structural Chunking | ✅ | header_then_token + fixed_size; code units via AST |
| 4 | Text Embedding & Indexing | ✅ | llama-cpp GGUF + hashing fallback; manifest; rebuild |
| 5 | Hybrid Search | ✅ | FTS5 + dense + RRF + filters |
| 6 | Grounded QA | ✅ | citations, abstention, prompt modes, audit trail |
| 7 | Code Awareness | 🟡 | code loader/chunker exist; **no language registry, no repo-level ingestion (git awareness)** |
| 8 | Spatiotemporal Metadata | ✅ | raster_scene/vector_layer + RTree + temporal fields + filters |
| 9 | Satellite Imagery Support | 🟡 | reader/tiler/preview/spectral work; nodata/CRS edge cases undertested; tiling not integrated into default ingest flow for large scenes |
| 10 | Multimodal Image Search | ❌→🟡 | `PlaceholderVisionEmbedder` stub + experimental `LlamaCppVisionEmbedder`; not wired into default pipeline or dashboard |
| 11 | Feedback & Evaluation | ✅ | events → dedup → review queue → 4 export types; metrics suite |
| 12 | Streamlit Reference App | ✅ | dashboard with 8 pages, public-API-only rule enforced |
| 13 | Provenance & Traceability | ✅ | SHA-256 chain asset→revision→segment→citation |
| 14 | Python API | ✅ | facade + models + exceptions exported; typed strict |
| 15 | Offline-First Execution | ✅ | offline default; lazy heavy imports |

## 2. Missing capabilities vs stated direction

1. **Agent Interface** — nothing serves agents today (no REST API, no MCP server). The library is import-only; programmatic remote access requires writing a wrapper.
2. **Background job execution** — `job` table + states exist but nothing consumes the queue asynchronously; ingestion is synchronous.
3. **Scalable vector search** — brute-force numpy only; no ANN (HNSW/IVF) path for >~50k segments.
4. **Multilingual support** — `--language fa` accepted at init, stored in settings, but query parser, abstention heuristics, and prompts are English-only.
5. **Model lifecycle** — no model download/verification helper; no embedding-space migration when model changes (stale index detection exists via checksums but no auto-rebuild).
6. **Blob GC / retention** — deleted assets leave orphaned objects; no compaction.

## 3. Architectural bottlenecks

| Bottleneck | Impact | Where |
|---|---|---|
| Facade god-object (1152 LOC, inline SQL + orchestration) | Change risk, test difficulty | `core/workspace.py` |
| Duplicated RRF + dual search paths | Behavior drift between facade/service paths | workspace.py vs retrieval/ |
| Synchronous everything | Large ingests block UI/CLI; no parallelism | ingest pipeline, job queue |
| Single SQLite writer | Concurrent processes (CLI while dashboard open) can hit busy-lock | storage/database.py — no retry/backoff |
| Filter-after-fusion ordering | top_k recall loss before top_n cut | retrieval/search_service.py |

## 4. Scaling risks

- Dense search O(n): corpus growth degrades linearly; memory holds all vectors per space.
- FTS5 fine to millions of rows, but `segments_fts` external-content triggers add write cost on bulk re-ingest.
- RetrievalRun/results JSON blobs grow unbounded (every search logged, never pruned).
- Object store grows monotonically (no GC); workspace dir size ≈ raw corpus forever.
- No batching/streaming in embed step → RAM spikes on large rebuilds.

## 5. Security risks (local-first context)

- Low overall: parameterized SQL, hex-hash object keys, no network surface.
- Watch items if a server layer is added later: no auth concept anywhere, MIME sniffing by extension only (`_detect_mime`), unvalidated model file paths from settings, Persian/user text injected verbatim into prompts (prompt-injection via documents is inherent to RAG — abstention+citations mitigate).

## 6. Technical debt summary

See [current-state/tech-debt.md](current-state/tech-debt.md) for full list. Top items:
1. duplicate `_rrf_fuse`, 2. no CI enforcing ruff/mypy/pytest/coverage, 3. legacy `apps/app.py`,
4. missing direct tests (query_parser, deduplicator, job_queue, prompts, events, plugin_registry),
5. DOCX dep without loader, 6. half-built async job story.

## 7.5 Debt status update (post audit — commit: dedupe-RRF)

- ✅ Removed duplicate `_rrf_fuse` in `core/workspace.py`; facade now uses canonical `rrf_fuse` from `retrieval/fusion`.
- ✅ Removed duplicate `_hit_sensor`; facade and `SearchService` share `hit_sensor()` + new `apply_hit_filters()` (spatial → temporal → sensor).
- ⏳ Remaining: route facade retrieval through `SearchService` with sparse/dense backend adapters (roadmap v0.1 item 1).

## 7. Recommended milestones (summary — details in roadmap)

- **v0.1**: consolidate (kill duplication, CI, close test gaps, docx decision)
- **v0.2**: harden RS + vision path, ANN backend behind existing protocol
- **v0.3**: agent/API surface + real background worker + multilingual groundwork
- **v1.0**: stability contract, packaging, docs site, benchmark baselines
