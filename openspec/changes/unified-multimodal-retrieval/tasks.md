# Tasks: unified-multimodal-retrieval

- [ ] Task 1: ImageRetrievalBackend adapter
  - Acceptance: `ImageRetrievalBackend` implements `RetrievalBackend`; `search()` loads query text via vision embedder's `embed_texts()` (or falls back to zero vector), queries `ImageIndex`, returns `SearchHit` list with `metadata.modality="image"`.
  - Verify: unit test — backend returns hits for populated index, empty list for empty index, respects top_k.
  - Files: `src/geomemory/index/image_backend.py` (new), `tests/unit/test_image_backend.py`

- [ ] Task 2: SearchRequest modality field
  - Acceptance: `SearchRequest.modalities` field added (`Text | Literal["image", "both"] | None`); `SearchResult` hits carry optional `modality` in metadata. Backward-compatible: omitting the field preserves existing behavior.
  - Verify: Pydantic validation test for valid/invalid modalities values.
  - Files: `src/geomemory/core/models.py`

- [ ] Task 3: SearchService modality dispatch
  - Acceptance: `SearchService.search()` inspects `request.modalities`; when `"both"`, appends `ImageRetrievalBackend` results to the fusion groups; applies modality weight factor (default 0.7) before RRF; skips image branch when image index has < 5 entries.
  - Verify: integration test — both-modalities search on workspace with text + image data returns mixed hits; text-only search unchanged.
  - Files: `src/geomemory/retrieval/search_service.py`, `tests/integration/test_multimodal_search.py`

- [ ] Task 4: Server search endpoint extension
  - Acceptance: `POST /api/v1/search` accepts optional `modalities` field; passes it through to `ws.search()`. `POST /api/v1/ask` accepts optional `modalities` field. Both return hits with modality metadata.
  - Verify: server test for both endpoints with modalities param present and absent.
  - Files: `server/src/geofront_api/routers/search.py`, `server/src/geofront_api/routers/ask.py`, `server/tests/test_search_modalities.py`

- [ ] Task 5: Web search-page modality toggle
  - Acceptance: Search page adds a toggle (text / image / both) wired to the `modalities` field in the API call. Results render with a small modality badge on each hit. Default is text-only.
  - Verify: `pnpm test` passes for SearchPage component; visual smoke test in browser.
  - Files: `apps/web/src/features/search/SearchPage.tsx`, `apps/web/src/features/search/SearchPage.test.tsx`

- [ ] Task 6: Gates
  - Acceptance: full geomemory + server test suites green; ruff/mypy clean; web build succeeds.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests server/tests -q && conda run -n geospatial ruff check libs/geomemory/src server/src && conda run -n geospatial mypy --strict libs/geomemory/src/geomemory && cd apps/web && pnpm build`
  - Files: all above

Dependencies: 1→2 (model change), 1→3 (backend used by service), 3→4 (server uses service), 4→5 (API contract), all→6.

Note: Task 1 assumes Change 2's OLMoEarth production wiring is complete (image index populated on ingest). If Change 2 is not yet applied, Task 1 can be implemented against a manually-populated test index.
