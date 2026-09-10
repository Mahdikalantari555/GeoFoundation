# Tasks: evolutionary-memory-engine-complete

- [x] Task 1: Scorer unit tests
  - Acceptance: `tests/unit/test_scoring.py` covers base score, all positive/negative signal combinations, threshold boundaries (13→supported, 14→verified, 7→proposed), clamping at 0 and 20.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests/unit/test_scoring.py -v`
  - Files: `tests/unit/test_scoring.py`

- [x] Task 2: CandidateMemoryRepository state-transition tests
  - Acceptance: Tests cover `promote(proposed→supported)`, `promote(supported→verified)`, `promote(any→rejected)`, invalid regression `verified→proposed` returns None, audit_trail records reviewer_id+note+timestamp on every transition.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests/unit/test_candidate_memory.py -v`
  - Files: `tests/unit/test_candidate_memory.py`

- [x] Task 3: Promotion-pipeline integration test
  - Acceptance: `tests/integration/test_candidate_pipeline.py` verifies that `FeedbackService.promote_to_candidate(event_ids, content)` creates a CandidateMemory with correct score, and that calling `CandidateMemoryService.score()` with signals updates state when thresholds are crossed.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests/integration/test_candidate_pipeline.py -v`
  - Files: `tests/integration/test_candidate_pipeline.py`

- [x] Task 4: Suggest-correction server endpoint
  - Acceptance: `POST /api/v1/ask/{turn_id}/suggest` creates a CandidateMemory linked to the turn; returns 404 when turn missing, 400 when content empty, 201 with candidate JSON on success. Turn is resolved via `get_state().require_workspace()` then queried from the `turn` table.
  - Verify: `conda run -n geospatial pytest server/tests/test_ask_suggest.py -v`
  - Files: `server/src/geofront_api/routers/ask.py` (new endpoint), `server/tests/test_ask_suggest.py`

- [x] Task 5: Ask-page correction UI
  - Acceptance: `AskPage.tsx` renders a "suggest correction" button below each assistant message with citations; clicking opens an inline text area; submitting calls `opsApi.suggestCorrection(turnId, content)`; input clears on success; button hidden when `qa.citations.length === 0`.
  - Verify: `cd apps/web && pnpm test -- src/features/ask/AskPage.test.tsx`
  - Files: `apps/web/src/features/ask/AskPage.tsx`, `apps/web/src/features/ask/AskPage.test.tsx`, `apps/web/src/api/ops.ts` (add `suggestCorrection`)

- [x] Task 6: Register change under openspec
  - Acceptance: `openspec status --change evolutionary-memory-engine-complete` shows proposal, specs, design as done; `openspec validate --change evolutionary-memory-engine-complete` passes.
  - Verify: `openspec validate --change evolutionary-memory-engine-complete`
  - Files: `.openspec.yaml` already created by scaffolding

- [x] Task 7: Gates
  - Acceptance: full geomemory test suite green; ruff/mypy clean for touched files; web build succeeds.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests -q && conda run -n geospatial ruff check libs/geomemory/src server/src/apps/web/src && conda run -n geospatial mypy --strict libs/geomemory/src/geomemory && cd apps/web && pnpm build`
  - Files: all above

Dependencies: 1→2 (same module), 1+2→3, 4 independent, 5 depends on 4 (API contract), 6 independent, all→7.
