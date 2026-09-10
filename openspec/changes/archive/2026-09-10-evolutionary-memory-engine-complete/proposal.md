## Why

The evolutionary-memory-engine scaffolding (CandidateMemory model, MemoryScorer, ProposalEngine, 3 SQLite tables, server routes, ReviewPage UI) is already implemented but untested and unreachable from normal user flows. Feedback events accumulate with no path into the candidate store; users see a review dashboard that nobody can populate. The engine is structural dead weight until the feedback→candidate pipeline is wired end-to-end and tested.

## What Changes

- Add unit and integration tests covering MemoryScorer, CandidateMemoryRepository state transitions, and the promotion pipeline (feedback event → candidate with scoring).
- Add a "suggest correction" control on each assistant message in the Ask page. When accepted, it calls a new server endpoint `POST /api/v1/ask/{turn_id}/suggest` that creates a `CandidateMemory` linked to the originating turn, source segments, and the corrected text — no manual copy-paste into the review dashboard required.
- Register the previously-manually-scaffolded `evolutionary-memory-engine` change via `openspec new change` so its specs are tracked.
- Close the scoring-edge-case gap: add test coverage for score-reversal (rejection drops state) and multi-actor agreement.

## Capabilities

### New Capabilities
- `candidate-memory-completion`: Test coverage + ask-page-to-candidate creation flow that makes the existing engine usable without manual API calls.

### Modified Capabilities
- None — all behavior additions are backward-compatible. Existing `candidate_memory`, `knowledge_change_proposal`, `provenance_chain` tables are extended with tests and a new server route; no existing requirement is altered.

## Impact

- **Code**: `tests/unit/test_scoring.py`, `tests/unit/test_candidate_memory.py`, `tests/integration/test_candidate_pipeline.py`; `server/src/geofront_api/routers/ask.py` (new `suggest` endpoint); `apps/web/src/features/ask/AskPage.tsx` (correction input); `apps/web/src/api/search.ts` (new suggest API call).
- **APIs**: Additive only — `POST /api/v1/ask/{turn_id}/suggest`.
- **Deps**: None new.
- **Risks**: Scoring threshold hard-codes are unchanged (existing design); the correction UI adds one new interaction point per answer but reuses the existing feedback event schema.
