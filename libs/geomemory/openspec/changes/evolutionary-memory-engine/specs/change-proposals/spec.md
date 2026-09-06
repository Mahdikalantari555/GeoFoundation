## Purpose
Generate diff-based knowledge change proposals from verified candidate memories, with human approval workflow.

## ADDED Requirements

### Requirement: KnowledgeChangeProposal model
The system SHALL define `KnowledgeChangeProposal` with fields: `id`, `proposal_type` (graph_relation|markdown_document|metadata_update|entity_create), `diff` ({original, proposed}), `source_candidate_ids` (JSON), `confidence` (float), `status` (pending|approved|rejected), `created_at`, `reviewed_at`, `reviewer_id`, `review_note`.

#### Scenario: Auto-generate from verified candidate
- **WHEN** a candidate reaches verified state
- **THEN** `ProposalEngine.generate()` creates a pending proposal with diff populated from candidate content.

#### Scenario: Approve proposal applies knowledge
- **WHEN** reviewer approves a graph_relation proposal
- **THEN** the relation is inserted into the authoritative knowledge graph; proposal status becomes approved; candidate linked.

### Requirement: ProposalEngine
`ProposalEngine` SHALL watch verified candidates and generate proposals. Max 5 proposals per session to prevent spam.

#### Scenario: Rate limit
- **WHEN** 5 proposals already generated in current session
- **THEN** further verified candidates queue for next session; no proposal created.

### Requirement: Reviewer API
Routes SHALL support: `GET /api/v1/feedback/proposals`, `POST /api/v1/feedback/proposals/{id}/approve`, `POST /api/v1/feedback/proposals/{id}/reject`.

#### Scenario: Approve with note
- **WHEN** reviewer calls approve with note "NDWI claim confirmed by domain expert"
- **THEN** proposal status approved, review_note stored, related candidate marked verified.
