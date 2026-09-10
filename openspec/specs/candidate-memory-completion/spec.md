# candidate-memory-completion Specification

## Purpose
Completes the candidate-memory subsystem by making it testable and reachable from normal user interactions — specifically the ask-page correction flow and the scoring state-machine edge cases.

## Requirements

### Requirement: Score-reversal on rejection
The MemoryScorer SHALL decrease a candidate's confidence when a rejection signal arrives, and SHALL transition the candidate back to a lower state when the score drops below the next-threshold boundary.

#### Scenario: Rejection drops verified to proposed
- **WHEN** a candidate with score 15 (verified) receives a rejection signal (−5)
- **THEN** the new score is 10 and the state transitions from `verified` to `supported`

#### Scenario: Double rejection drops below proposed
- **WHEN** a candidate with score 8 (supported) receives two rejections (−10 total)
- **THEN** the new score is clamped to 0 and the state becomes `proposed`

### Requirement: Multiple-actor agreement bonus
The MemoryScorer SHALL add +3 to a candidate's confidence when at least two distinct authors have submitted confirming feedback for the same candidate.

#### Scenario: Two different users confirm
- **WHEN** author A confirms a candidate and author B separately confirms the same candidate
- **THEN** the candidate's score includes the +3 multiple-actors bonus

#### Scenario: Same user confirms twice
- **WHEN** a single author submits two confirming events for the same candidate
- **THEN** no multiple-actors bonus is applied (only distinct authors count)

### Requirement: Suggest-correction endpoint
The server SHALL accept a correction suggestion attached to a conversation turn and persist it as a CandidateMemory linked to that turn and its source segments.

#### Scenario: Suggest correction on answered turn
- **WHEN** the Ask page sends `POST /api/v1/ask/{turn_id}/suggest` with `content` and optional `memory_type`
- **THEN** a CandidateMemory is created with `source_feedback_ids` containing the turn id, the suggested text stored as content, and an initial score computed from the default base (5)

#### Scenario: Missing turn rejects suggestion
- **WHEN** the suggested turn id does not exist in the workspace
- **THEN** the endpoint returns 404 with code `turn_not_found`

#### Scenario: Empty content rejects suggestion
- **WHEN** the suggest body omits `content` or sends an empty string
- **THEN** the endpoint returns 400 with code `empty_content`

### Requirement: Ask-page correction UI
The Ask page SHALL expose a "suggest correction" control on each assistant message that has citations, allowing the user to propose a modified answer text.

#### Scenario: Correction input shown with citations
- **WHEN** an assistant message renders with one or more citations
- **THEN** a "suggest correction" button is visible below the answer

#### Scenario: Submitted correction creates candidate
- **WHEN** the user types a correction and submits it
- **THEN** the server creates a CandidateMemory and the UI shows a confirmation state; the input field clears

#### Scenario: Correction input hidden without citations
- **WHEN** an assistant message has zero citations (abstention or no evidence)
- **THEN** the "suggest correction" control is not rendered

### Requirement: Test coverage for candidate lifecycle
Unit tests SHALL cover every public method of CandidateMemoryRepository and MemoryScorer, including all valid state-transition paths and invalid-transition rejections.

#### Scenario: All state transitions tested
- **WHEN** tests execute for `proposed→supported`, `supported→verified`, `any→rejected`
- **THEN** each transition verifies the audit_trail records the reviewer id and note, and the updated_at timestamp advances

#### Scenario: Invalid transition rejected
- **WHEN** code attempts `verified→proposed` (regression backward)
- **THEN** the repository returns None and the state is unchanged
