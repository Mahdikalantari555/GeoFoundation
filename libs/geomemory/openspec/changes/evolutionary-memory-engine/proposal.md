# Proposal: evolutionary-memory-engine

## Why

GeoMemory has raw feedback plumbing (`FeedbackEvent`, `ReviewQueue`, JSONL export)
but no **memory scoring**, no **candidate memory store** isolated from authoritative
knowledge, no **change proposal** workflow, and no frontend for human review.

The result: user corrections live as flat review-queue rows, never influence retrieval
ranking, never generate knowledge-graph proposals, and lack the confidence-evolution
loop the domain needs for safe, auditable knowledge growth.

## What Changes

### Candidate Memory Store
- New `CandidateMemory` model + SQLite table `candidate_memory` (immutable append-only).
- States: `proposed` → `supported` → `verified` / `rejected`.
- Stored separately from `feedback_event` / `dataset_example`.
- `CandidateMemoryService` CRUD + state transitions + audit trail (`provenance_chain`).

### Memory Scoring Engine
- `MemoryScorer` computes dynamic confidence from signals:
  - Positive: user confirms, multiple similar feedback, retrieval improvement, repeated references.
  - Negative: user rejects, contradictory evidence, reviewer flags, retrieval degradation.
- Score range 0–20; thresholds: `≥14 verified`, `≥8 supported`, else `proposed`.
- Rejected memories preserve score/audit history; excluded from retrieval.

### Change Proposal System
- `KnowledgeChangeProposal` model: diff format (`original`, `proposed`, `source_candidate_ids`, `confidence`, `status`).
- Types: `graph_relation`, `markdown_document`, `metadata_update`, `entity_create`.
- Auto-generated from `verified` candidate memories via `ProposalEngine`.
- Reviewer workflow: approve → apply to authoritative store; reject → mark rejected.

### Retrieval Integration
- Retrieval priority order:
  1. Verified Knowledge
  2. Approved Graph Relations
  3. High-Confidence Candidate Memories (score ≥14)
  4. Low-Confidence Candidate Memories (score ≥8)
- Candidate memories never overwrite authoritative knowledge directly.

### Web Review UI
- New **Feedback & Review** page (extends existing):
  - Candidate list with score, state, source feedback refs.
  - Diff viewer (original vs proposed) with approve/reject actions.
  - Knowledge Change Dashboard: pending proposals, approved changes, rejected history.
- Settings: enable/disable candidate memory retrieval influence.

## Capabilities

### New Capabilities
- `candidate-memory-store`: append-only candidate memories with state machine + audit trail.
- `memory-scoring-engine`: confidence scoring from multi-signal feedback.
- `change-proposals`: diff-based knowledge proposals from verified candidates.

### Modified Capabilities
- `feedback-layer`: extends `FeedbackEvent` → `CandidateMemory` promotion pipeline.
- `retrieval-layer`: candidate-aware ranking tiers.
- `web-app`: Feedback & Review page with diff viewer + dashboard.

## Impact

- **Code**: `src/geomemory/core/models.py` (+3 models), `src/geomemory/storage/schema.sql` (+3 tables), `src/geomemory/feedback/candidate_memory.py`, `src/geomemory/feedback/scoring.py`, `src/geomemory/feedback/proposals.py`, `src/geomemory/services/candidate_memory_service.py`, `server/src/geofront_api/routers/feedback.py` (extend), `apps/web/src/features/feedback/` (new UI).
- **APIs**: additive routes under `/api/v1/feedback/candidates`, `/api/v1/feedback/proposals`.
- **Deps**: none new.
- **Risks**: scoring heuristics need calibration; candidate retrieval overhead must stay bounded (cap at top-K per tier).
