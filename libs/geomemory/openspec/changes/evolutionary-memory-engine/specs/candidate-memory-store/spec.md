## Purpose
Add a first-class candidate memory store isolated from authoritative knowledge, with confidence scoring, state machine, and audit trail.

## ADDED Requirements

### Requirement: CandidateMemory model
The system SHALL define `CandidateMemory` with fields: `id`, `content`, `memory_type` (fact|correction|annotation|preference), `source_feedback_ids` (JSON list), `confidence_score` (0–20 float), `state` (proposed|supported|verified|rejected), `created_at`, `updated_at`, `author`, `audit_trail` (JSON list of {action, timestamp, reviewer_id, note}).

#### Scenario: State transition
- **WHEN** a candidate is promoted from proposed → supported → verified
- **THEN** each transition appends an audit entry and updates `updated_at`; score is recomputed by `MemoryScorer`.

#### Scenario: Rejection preserves history
- **WHEN** a candidate is rejected
- **THEN** state becomes rejected, score preserved, audit trail records rejection reason, candidate excluded from retrieval.

### Requirement: CandidateMemoryService
`CandidateMemoryService` SHALL provide: `create(content, memory_type, source_feedback_ids)`, `get(id)`, `list(state=None)`, `promote(id, new_state, reviewer_id, note)`, `score(id)`, `search(query, min_score=0)`.

#### Scenario: Promote with audit
- **WHEN** `promote()` is called with valid transition
- **THEN** state updates, audit_trail appends {action: "promote", to_state, reviewer_id, note, timestamp}.
