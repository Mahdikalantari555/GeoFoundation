## Purpose
Expose candidate memories, scoring, and change proposals in the web app for human review.

## ADDED Requirements

### Requirement: Feedback & Review page
A new page at `/feedback` SHALL display:
- Candidate list with score badge, state badge, memory type, author, created_at.
- Filters: state (proposed/supported/verified/rejected), min_score, memory_type.
- Actions: promote (proposed→supported, supported→verified), reject, view source feedback.

#### Scenario: Promote candidate
- **WHEN** user clicks "Promote to Supported" on a proposed candidate
- **THEN** POST `/api/v1/feedback/candidates/{id}/review` with action=promote, new_state=supported; UI refreshes and shows updated score/state.

### Requirement: Diff Review Interface
Each candidate with a pending proposal SHALL show:
- Side-by-side original vs proposed.
- Source references (linked feedback events).
- Confidence score.
- Reviewer comment box.

#### Scenario: Review diff
- **WHEN** user opens a candidate with a pending graph_relation proposal
- **THEN** diff shows current relation vs proposed relation; approve/reject buttons visible; comment optional.

### Requirement: Knowledge Change Dashboard
Dashboard SHALL show:
- Pending proposals count.
- Approved changes (last 30 days).
- Rejected proposals (last 30 days).
- Historical changes (link to authoritative knowledge graph diff).

#### Scenario: Dashboard counts
- **WHEN** there are 3 pending, 12 approved, 2 rejected proposals
- **THEN** dashboard displays these counts with trend indicators.

### Requirement: i18n
All new strings SHALL have `en` and `fa` translations in `apps/web/src/i18n/*.json`.
