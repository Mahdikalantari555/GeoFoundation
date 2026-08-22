# ADR-0005: Hybrid Retrieval with Reciprocal Rank Fusion

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

Sparse keyword search (FTS5) is precise but misses paraphrases; dense embeddings are semantic but weak on exact terms/symbols/ids common in remote-sensing literature (sensor names, index acronyms). The system needs both without a learned re-ranker (CPU-only constraint).

## Decision

`retrieval/search_service.SearchService` orchestrates:

1. `QueryParser.parse()` cleans query, extracts inline filters, detects intent.
2. Query fans out to all configured backends (sparse FTS5 adapter + dense vector backend).
3. Results fused by **Reciprocal Rank Fusion** (`retrieval/fusion.py:rrf_fuse`, k=60) for hybrid mode; single-backend passthrough for sparse/dense; `linear_fuse` as alternate mode.
4. Post-fusion pipeline: exact dedup → per-document diversity cap (`max_per_document=3`) → spatial filter → temporal filter → sensor filter → truncate to `top_n`.
5. Every search persists a `RetrievalRun` (query plan, filters, latency) — full audit trail.

Filters operate on hit metadata produced at ingest time (bbox in `spatial_index` RTree / locator JSON / raster_scene sensor), keeping the query path dependency-light.

## Consequences

- ✅ No model training or reranker needed; robust default quality.
- ✅ Deterministic and explainable; retrieval runs are replayable from logs.
- ❌ Known debt: a second private `_rrf_fuse` exists inside `core/workspace.py` — must be unified (tech-debt #2).
- ❌ Filter-after-fusion ordering means top_k recall can shrink before top_n truncation; acceptable now, revisit if recall metrics degrade.
