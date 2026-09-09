## Context

`SearchService` (`retrieval/search_service.py`) already accepts a list of `RetrievalBackend` instances and fuses their results via RRF. The missing piece is an `ImageRetrievalBackend` adapter that wraps `ImageIndex` and produces `SearchHit` objects compatible with the fusion pipeline. The ONNX spike outcome (Change 2) determines whether one or two vision spaces exist; this design targets the more complex case (two spaces) and notes the simplification if ONNX is abandoned.

## Goals / Non-Goals

**Goals:**
- Add `ImageRetrievalBackend` implementing `RetrievalBackend`.
- Extend `SearchRequest` and `SearchResult` with modality metadata.
- Wire modality dispatch into `SearchService.search()`.
- Add UI toggle on the web search page.

**Non-Goals:**
- Cross-modal embedding (a single vector representing text+image combined) — deferred.
- Learned reranking across modalities — RRF is sufficient for now.
- Real-time multi-query parallelism — sequential backend calls are acceptable at this scale.

## Decisions

### D1. Image query embedding via vision embedder, not text embedder
When `modalities="both"`, the image backend receives the raw query string, runs it through the vision embedder's `embed_texts()` method (which returns None for OLMoEarth — image-only model), and falls back to using the first image in the user's session context or skipping the image branch. For the initial release, text queries with `modalities="both"` trigger image search using a **zero vector** fallback (returns top-k most recent images) while text search runs normally; a follow-up task adds text-to-image embedding when a cross-modal model becomes available.

Alternative considered: requiring an image upload alongside every both-modalities query. Rejected because it raises the interaction barrier too high for the first iteration.

### D2. Modality weight in RRF
Image hits get a 0.7 multiplier on their RRF contribution. This prevents a small image index from flooding results when text retrieval is strong, while still allowing image hits to rank highly when they match well. The factor is configurable via `SearchRequest.modality_weight`.

### D3. Single result list with modality badge
Rather than returning two separate hit lists, all hits are fused into one `SearchResult.hits` list. Each hit carries `metadata.modality` (`"text"` or `"image"`) so the UI can render badges. The API consumer decides how to display them.

## Risks / Trade-offs

- [Zero-vector fallback noise] → Returning top-k most-recent images for unguided queries may surface irrelevant results. Mitigation: only activate image branch when `modalities="both"` and the query has non-trivial text; if text dense score is near zero, skip image branch.
- [Two vision spaces] → If Change 2's ONNX spike produces a second space, the image backend must query both spaces and merge. Design accommodates this via a list of image-space ids in `SearchRequest`. If ONNX is abandoned, the list has one entry.

## Migration Plan

All additions are backward-compatible. `modalities` defaults to `None` (current behavior). Existing callers are unaffected.

## Open Questions

- Should the modality weight be a workspace-level setting (per-workspace tuning) or a request-level override? Recommendation: request-level for flexibility; workspace default can be added later.
- When should the image branch be skipped even in `both` mode — e.g., if the image index has fewer than N entries? Threshold TBD, proposed: skip if < 5 image embeddings exist.
