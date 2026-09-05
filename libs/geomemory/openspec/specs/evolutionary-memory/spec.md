# Evolutionary Memory — Specification

Governed, human-in-the-loop knowledge refinement for GeoMemory. Candidate memories carry expertise as evidence, never as direct mutations of authoritative knowledge; promotion requires explicit approval.

## Requirements

### Requirement: Layered knowledge architecture
The system SHALL maintain two disjoint layers: an authoritative knowledge base (curated papers, reports, manuals, approved markdown/graph entities, version-controlled and auditable) and a candidate memory store (user-generated feedback, writable during conversations). Direct mutation of the authoritative layer from conversational feedback SHALL be prohibited.

#### Scenario: Feedback is isolated
- **WHEN** a user submits a correction or annotation via any feedback type
- **THEN** the content is persisted to the candidate store only, with `status=proposed` and a confidence score, and the authoritative KB remains unchanged

#### Scenario: Authoritative immutability
- **WHEN** a retrieval or QA operation reads the authoritative KB
- **THEN** no candidate memory is ever written into its tables or graph without a preceding approved proposal

### Requirement: Candidate memory store
Every feedback submission SHALL be stored as an addressable candidate memory with fields `{id, author, timestamp, source_turn_id, type, original_text, proposed_text, confidence, status}` and linked provenance (`answer→citation→segment→asset_revision` when applicable).

#### Scenario: Correction creates candidate
- **WHEN** a user edits "Salinity stress primarily affects NDVI." to "Salinity stress often affects NDVI, but thermal indicators may respond earlier."
- **THEN** a candidate memory is created with `type=correction`, `status=proposed`, and is excluded from the authoritative KB until review

#### Scenario: Annotation creates fact
- **WHEN** a user adds "Under arid conditions, canopy temperature often separates water stress from salinity more effectively than spectral indices."
- **THEN** it is stored as `type=annotation`, `status=proposed`, with confidence initialized low

### Requirement: Memory scoring engine
Each candidate memory SHALL carry a dynamic confidence score that evolves from positive and negative signals. Positive signals: user confirmation, multiple similar feedbacks, improved retrieval outcomes, repeated referencing. Negative signals: rejection, contradictory evidence, reviewer flag, degraded retrieval. Scores SHALL be recomputed deterministically and be monotonic with respect to accumulated evidence.

#### Scenario: Confirm raises score
- **WHEN** a second user or the same user confirms a memory that previously scored 12
- **THEN** the score increases and `status` may transition `proposed → supported` per thresholds

#### Scenario: Flag lowers score
- **WHEN** a reviewer flags or contradictory evidence is recorded against a candidate
- **THEN** the score decreases and the memory is excluded from promotion eligibility until re-validated

### Requirement: Memory lifecycle states
Candidate memories SHALL move through states `proposed → supported → verified → (rejected|approved)`. `proposed` is unverified/low-confidence/not trusted; `supported` has positive evidence and appears in the review queue and may influence ranking; `verified` is reviewer-approved and eligible to generate knowledge proposals; `rejected` is preserved for audit, excluded from retrieval and ranking, and cannot affect future results.

#### Scenario: State transitions
- **WHEN** a memory accumulates sufficient positive signals and passes validation
- **THEN** its state advances to `supported` and it becomes eligible for the review dashboard

#### Scenario: Rejected is inert
- **WHEN** a memory is marked `rejected`
- **THEN** it remains readable in history but is filtered from all retrieval and fusion paths

### Requirement: Feedback types
The system SHALL support four feedback types with distinct handling:
1. Simple rating (`helpful`/`not_helpful`) adjusts confidence only.
2. Answer correction (edited response span) creates a candidate memory with original/proposed diff.
3. Expert annotation (free-form domain note) creates a candidate fact.
4. Retrieval feedback (e.g., "This paper is outdated") updates source quality metadata, not textual knowledge.

#### Scenario: Rating only scores
- **WHEN** a user clicks Helpful on an answer
- **THEN** no new candidate is created, but linked memories' scores are incremented

#### Scenario: Retrieval feedback marks source
- **WHEN** a user flags a source as outdated
- **THEN** the asset's quality metadata is updated and its future retrieval priority is reduced, without mutating the document content

### Requirement: Knowledge update workflow
Promotion SHALL follow `User Feedback → Candidate Memory → Validation → Change Proposal → Human Review → Approved Knowledge Update`. Validation checks provenance, contradiction with authoritative KB, and retrieval impact. Proposals generate concrete artifacts (new/modified markdown document, graph relation, metadata patch) and remain `pending` until a human reviewer approves or rejects with comments.

#### Scenario: Proposal generation
- **WHEN** a `verified` candidate "NDWI is usually more sensitive than NDVI for early water stress in sugarcane." reaches the proposal stage
- **THEN** the system emits a proposal containing the target artifact diff, source references, confidence, and author, with status `pending_approval`

#### Scenario: Approval merges
- **WHEN** a reviewer approves a proposal
- **THEN** the authoritative KB is updated atomically (new revision, graph edge, or document patch), provenance records `{original, proposed, author, timestamp, confidence, approval_history}`, and the candidate is marked `approved`

### Requirement: Knowledge graph proposal integration
Candidate memories that imply entities/relations SHALL generate graph proposals (e.g., `NDWI —responds_earlier_than→ NDVI`, `NDWI —sensitive_to→ Water Stress`) that remain `proposed` and invisible to traversal/ranking until approved. Approved relations become first-class graph edges with provenance to the source candidate.

#### Scenario: Proposed edge is invisible
- **WHEN** a graph proposal `NDWI responds_earlier_than NDVI` is pending
- **THEN** queries traversing the knowledge graph do not follow that edge

#### Scenario: Approved edge is traversable
- **WHEN** the proposal is approved
- **THEN** subsequent QA and retrieval that consult the graph include the new edge and cite the candidate as source

### Requirement: Retrieval priority with candidate memories
Retrieval SHALL prioritize verified knowledge over candidates. Ranking order: (1) verified KB segments, (2) approved graph relations, (3) high-confidence candidates (`supported`/`verified` meeting threshold), (4) low-confidence candidates (`proposed`). Low-confidence candidates SHALL NOT outrank authoritative hits for the same query.

#### Scenario: Authoritative dominance
- **WHEN** a query matches both an authoritative segment and a low-confidence candidate
- **THEN** the authoritative hit ranks higher in RRF fusion output

#### Scenario: High-confidence surfaces
- **WHEN** no authoritative hit exists but a high-confidence candidate matches
- **THEN** the candidate may appear in results with a `candidate` flag and lower weight

### Requirement: Auditability and reversibility
Every knowledge change SHALL preserve `{original_content, proposed_modification, author, timestamp, confidence, approval_history}` immutably. No information SHALL be permanently overwritten; all evolution is reversible via a revert proposal. History SHALL be queryable per entity and per proposal.

#### Scenario: Revert
- **WHEN** an approved change introduced "- Salinity primarily affects NDVI." → "+ Salinity affects NDVI, but canopy temperature often responds earlier."
- **THEN** history retains both sides, and a new revert proposal can restore the original with its own audit trail

### Requirement: Review interfaces (facade contracts)
The public facade SHALL expose operations for the frontend: per-answer actions (`upvote`, `downvote`, `edit_response`, `suggest_improvement`, `add_expert_note`, `view_sources`), a diff-review view (side-by-side original/proposed, source refs, confidence, reviewer comments), and a knowledge-change dashboard (`proposed`, `candidate_facts`, `pending_approvals`, `rejected`, `history`). The library SHALL NOT implement UI; it SHALL define the typed contracts that the gateway and web consume.

#### Scenario: Frontend reads proposals
- **WHEN** the dashboard calls `list_proposals(status=pending)`
- **THEN** it receives typed proposals with diffs, confidence, and source locators without importing library internals

### Requirement: Enterprise extensibility hooks
The design SHALL support, without breaking existing flows: multi-reviewer approval, organization-specific knowledge layers, role-based permissions (submit vs review vs approve), federated memory sharing, cross-project import/export, and automated proposal generation from usage analytics. These extensions SHALL be additive behind capability flags or new facade methods.

#### Scenario: Multi-reviewer gate
- **WHEN** an organization policy requires two approvals
- **THEN** a proposal remains `pending` after one approval and only transitions to `approved` on the second, with both reviewers recorded
