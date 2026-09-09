## Why

Text retrieval (FTS5 + dense vector) and vision retrieval (OLMoEarth image embeddings) operate as completely independent pipelines today. A user searching for "agricultural stress in Khuzestan 2018–2022" must run two separate queries and manually correlate results. The system's unique value — spatiotemporal remote-sensing memory — is undercut when visual evidence and textual evidence cannot be fused in a single ranked result set. Unified multimodal retrieval makes GeoMemory a single query surface for all knowledge types.

## What Changes

- Extend `SearchRequest` with a `modalities` field (`text`, `image`, `both`) so the search orchestrator knows which backends to activate.
- Add an `ImageRetrievalBackend` adapter that wraps `ImageIndex` and implements the `RetrievalBackend` protocol, enabling it to participate in RRF fusion alongside FTS5 and dense-text backends.
- When `modalities="both"`, text and image hits are fused via RRF; image hits carry a `modality="image"` flag so the UI can render them distinctly.
- The search API gains a `modalities` parameter; the Ask endpoint passes `modalities` through to search so grounded QA can cite both text segments and image scenes.
- Design is contingent on Change 2's ONNX outcome: if ONNX export succeeds, two vision spaces exist and the unified pipeline must support querying either or both; if ONNX fails, only the torch space exists and the design simplifies accordingly.

## Capabilities

### New Capabilities
- `unified-multimodal-retrieval`: Single query surface fusing text (FTS5 + dense), vision (OLMoEarth image index), spatial, temporal, and metadata filters into one RRF-ranked result set.

### Modified Capabilities
- `search-retrieval` (geomemory): extends requirements to include cross-modal fusion and modality-aware ranking weights.
- `vision-embedding` (geomemory): extends to define the image backend contract used by the unified searcher.

## Impact

- **Code**: `src/geomemory/retrieval/search_service.py` (modality dispatch); `src/geomemory/index/image_index.py` (backend adapter); `src/geomemory/core/models.py` (SearchRequest.modalities field); server router `routers/search.py` (new param); web search page (modality toggle).
- **APIs**: Additive — `POST /api/v1/search` gains optional `modalities` field; `POST /api/v1/ask` gains optional `modalities` field.
- **Deps**: None new (uses existing ImageIndex and sqlite-vec backends).
- **Risks**: RRF fusion across modalities with different score distributions requires normalization; candidate-memory tier weights must not dominate authoritative hits.
