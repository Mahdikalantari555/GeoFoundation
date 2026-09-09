## Context

CandidateMemory infrastructure is already wired: `candidate_memory` table exists in schema, `MemoryScorer` implements rule-based scoring, `CandidateMemoryRepository` handles CRUD + promote, `ProposalEngine` auto-generates proposals on verified candidates, the server exposes `GET/POST /feedback/candidates` and `/feedback/candidates/{id}/review`, and the web `ReviewPage` renders the review UI. What is missing: zero unit tests for any of these components, no ask-page-to-candidate creation path (the POST endpoint requires manual content), and no test coverage for score-reversal or multi-actor logic.

## Goals / Non-Goals

**Goals:**
- Add unit and integration tests covering scorer edge cases, repository state-machine transitions, and the promotion pipeline.
- Add `POST /api/v1/ask/{turn_id}/suggest` server endpoint that creates a CandidateMemory from a turn-context correction.
- Add a "suggest correction" control on the Ask page assistant message (visible only when citations exist).
- Register the existing hand-scaffolded change under openspec so its specs are tracked.

**Non-Goals:**
- Changing scoring thresholds or heuristics (hard-coded values stay as-is; calibration is future work).
- Adding contradiction detection beyond the existing negative signal stub.
- Modifying the ReviewPage UI or adding diff-viewer improvements.
- Multi-reviewer workflows or role-based permissions.

## Decisions

### D1. New endpoint instead of reusing existing POST /feedback/candidates
The existing candidate-creation endpoint requires the caller to assemble content and source_feedback_ids manually. The ask-page context already has `turn_id` and knows which segments were cited; a dedicated `POST /api/v1/ask/{turn_id}/suggest` endpoint lets the UI pass just `content` and `memory_type` and lets the server resolve the turn's citation chain into `source_feedback_ids`. This keeps the ask-page interaction simple and the server responsible for turning a turn id into a properly-linked candidate.

Alternative considered: extending `POST /feedback/candidates` with a `turn_id` optional field. Rejected because it would mix two concerns (generic candidate creation vs. ask-context suggestion) in one endpoint.

### D2. Correction control rendered only when citations exist
Showing the correction input on every answer (including abstentions) adds noise without value — abstentions have no cited evidence to correct. The control is gated on `qa.citations.length > 0`, matching the existing "show sources" button pattern.

Alternative considered: always show the control and let users suggest corrections to abstention reasoning. Rejected to keep the UI focused; users can always navigate to the Feedback page directly.

### D3. Tests live in libs/geomemory/tests (existing convention)
The geomemory library owns its own test suite. Server-side endpoint tests belong in `server/tests/`. Web component tests go in `apps/web/src/features/ask/AskPage.test.tsx` alongside the existing test file. This follows the established monorepo pattern documented in AGENTS.md.

## Risks / Trade-offs

- [Score threshold brittleness] → Thresholds (≥14 verified, ≥8 supported) remain hardcoded in MemoryScorer; future calibration work will need to update both the scorer and the test expectations simultaneously. Documented in Open Questions.
- [Turn not found races] → A turn could be deleted between the UI rendering the correction button and the user submitting. Mitigated by returning 404 rather than crashing; the UI should surface a "this answer is no longer available" message.
- [Multi-actor detection gap] → The current scorer checks `multiple_actors` as a boolean flag passed via signals, but there is no automated way to detect that two different authors confirmed the same candidate. The test adds the expectation that the flag is honored when set; actual auto-detection is deferred.

## Migration Plan

No schema changes. All additions are additive:
1. New test files (zero impact on existing behavior).
2. New server endpoint (backward-compatible; no existing routes touch `/ask/{id}/suggest`).
3. New UI control (progressive enhancement; existing ask flows unchanged).

Rollback: removing the new endpoint and UI control restores exact prior behavior.

## Open Questions

- Should the `suggest` endpoint also accept an explicit `memory_type` override, or default to `"correction"` for all ask-page submissions? Defaulting simplifies the UI; an override could be added later if domain-specific types are needed.
- When multiple correction suggestions target the same turn, should they create separate candidates or replace the previous draft? Current design creates separate candidates; this may need deduplication logic later.
