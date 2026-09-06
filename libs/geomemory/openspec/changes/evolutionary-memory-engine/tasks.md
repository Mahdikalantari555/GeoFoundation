# Tasks: evolutionary-memory-engine

- [ ] Task 1: Candidate Memory models + schema
  - Acceptance: `CandidateMemory` model with states proposed/supported/verified/rejected, confidence_score, source_feedback_ids, audit_trail; SQL migration adds `candidate_memory` + `provenance_chain` tables; existing tests green.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests -q && conda run -n geospatial ruff check src`
  - Files: `src/geomemory/core/models.py`, `src/geomemory/storage/schema.sql`, `src/geomemory/storage/migrations.py`

- [ ] Task 2: CandidateMemoryService + state transitions
  - Acceptance: CRUD + promote(state) with audit trail append; state transitions valid (proposed→supported→verified|rejected); rejected preserves history.
  - Verify: unit tests for all transitions + audit trail integrity.
  - Files: `src/geomemory/feedback/candidate_memory.py`, `src/geomemory/services/candidate_memory_service.py`, `tests/unit/test_candidate_memory.py`

- [ ] Task 3: MemoryScorer
  - Acceptance: rule-based scorer 0–20; positive/negative signals; thresholds ≥14 verified, ≥8 supported; deterministic given same inputs.
  - Verify: golden tests with fixed feedback patterns → expected scores.
  - Files: `src/geomemory/feedback/scoring.py`, `tests/unit/test_scoring.py`

- [ ] Task 4: Promotion pipeline (feedback → candidate → scored)
  - Acceptance: `FeedbackService` gains `promote_to_candidate(event_ids) -> CandidateMemory`; scoring applied at promotion; verified candidates emit `candidate_verified` event.
  - Verify: integration test: feedback events → candidate with expected score/state.
  - Files: `src/geomemory/services/feedback_service.py`, `tests/integration/test_candidate_pipeline.py`

- [ ] Task 5: Change Proposal engine
  - Acceptance: `ProposalEngine.generate(candidate)` creates `KnowledgeChangeProposal` for verified candidates; types graph_relation/markdown_document/metadata_update/entity_create; diff format.
  - Verify: unit tests for each proposal type + diff generation.
  - Files: `src/geomemory/feedback/proposals.py`, `tests/unit/test_proposals.py`

- [ ] Task 6: Reviewer API routes
  - Acceptance: `GET /api/v1/feedback/candidates`, `POST /api/v1/feedback/candidates/{id}/review`, `GET /api/v1/feedback/proposals`, `POST /api/v1/feedback/proposals/{id}/approve|reject`.
  - Verify: server tests for list/review/approve/reject flows.
  - Files: `server/src/geofront_api/routers/feedback.py`, `server/tests/test_feedback.py`

- [ ] Task 7: Web Feedback & Review UI
  - Acceptance: candidate list with score/state badges; diff viewer; dashboard with pending/approved/rejected; approve/reject actions wired to API.
  - Verify: `pnpm gen:api && pnpm lint && pnpm build && pnpm test`.
  - Files: `apps/web/src/features/feedback/FeedbackPage.tsx`, `apps/web/src/features/feedback/hooks.ts`, `apps/web/src/api/feedback.ts`, i18n keys.

- [ ] Task 8: Retrieval integration
  - Acceptance: candidate memories indexed in `text.candidates.*` space; retrieval fusion merges with tier weights (verified 0.8, supported 0.4, proposed 0.1); authoritative always dominates.
  - Verify: retrieval test with mixed authoritative + candidate hits asserts ranking order.
  - Files: `src/geomemory/retrieval/fusion.py`, `src/geomemory/services/index_service.py`, `tests/unit/test_fusion_candidates.py`

- [ ] Task 9: Gates
  - Acceptance: full suite green; ruff/mypy clean for touched files.
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests server/tests -q && conda run -n geospatial ruff check libs/geomemory/src server/src && conda run -n geospatial mypy --strict libs/geomemory/src/geomemory`

Dependencies: 1→(2,3), 2+3→4, 4→5, 5→6, 6→7, 8 independent, all→9.
