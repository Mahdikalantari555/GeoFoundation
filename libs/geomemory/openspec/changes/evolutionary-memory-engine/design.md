# Design: evolutionary-memory-engine

## Context

Feedback events (`FeedbackEvent`) and review queue (`DatasetExample`) already exist.
`FeedbackService.record_feedback()` appends events; `ReviewQueue.review()` moves
examples to accepted/rejected; CLI exports JSONL. What's missing: candidate memories
as first-class entities with confidence scores, state machine beyond pending/accepted/rejected,
auto-generated change proposals, and retrieval integration.

## Goals / Non-Goals

- Goals: confidence-scored candidate memories; proposed/supported/verified/rejected states;
  diff-based change proposals with human approval; retrieval tiers; full audit trail.
- Non-Goals: multi-reviewer workflows, role-based permissions, federated memory
  (future enterprise extensions), automatic approval without human review.

## Decisions

### D1. Separate Candidate Memory table
New `candidate_memory` table (not reuse `feedback_event` or `dataset_example`).
Rationale: feedback events are raw immutable signals; candidate memories are
derived, scored, stateful artifacts. Keeping them separate avoids schema coupling
and preserves feedback as evidence provenance.

Fields: id, content, memory_type, source_feedback_ids (JSON), confidence_score,
state (proposed/supported/verified/rejected), created_at, updated_at, author,
audit_trail (JSON list of {action, timestamp, reviewer_id, note}).

### D2. Scoring heuristics
Initial implementation uses rule-based scoring (0–20):
- Base: 5 for proposed.
- +3 per confirming feedback event (cap +6).
- +2 if retrieval usage count > threshold (cap +4).
- +3 if multiple actors agree (cap +3).
- -5 per rejection/flag.
- -3 per contradictory evidence.
Thresholds: ≥14 verified, ≥8 supported, else proposed.
Future: replace with learned scorer; keep interface stable.

### D3. Proposal generation
`ProposalEngine` watches for `verified` candidates and auto-generates
`KnowledgeChangeProposal` rows. Types:
- `graph_relation`: new Relation rows.
- `markdown_document`: proposed edits to curated markdown.
- `metadata_update`: asset/segment metadata changes.
- `entity_create`: new graph entity.
Proposals carry diff (original vs proposed), source candidate ids, confidence.
Status: `pending` → `approved` / `rejected`.

### D4. Retrieval integration
Candidate memories indexed in a separate `text.candidates.*` space.
Retrieval fusion adds candidate hits at reduced weight:
- verified: weight 0.8
- supported: weight 0.4
- proposed: weight 0.1
Authoritative results always rank higher (weight 1.0).

### D5. Frontend
New Feedback & Review page under `apps/web/src/features/feedback/`:
- Candidate list with score badges, state filters.
- Diff viewer (side-by-side, source refs, reviewer comments).
- Dashboard: pending/approved/rejected counts, recent activity.

## Risks / Trade-offs

- [Scoring drift] → thresholds are configurable; manual override via reviewer.
- [Retrieval latency] → candidate space capped at top-20 per query; merged after authoritative.
- [Proposal spam] → rate-limit auto-generation (max 5 proposals per session).

## Migration Plan

New tables only. Existing workspaces gain empty candidate_memory + proposal tables
on next open (schema migration v2). No data migration.

## Open Questions

- Should LanceDB be adopted as the primary vector backend before or after this change?
  Recommendation: parallel tracks — this change uses existing VectorBackend.
