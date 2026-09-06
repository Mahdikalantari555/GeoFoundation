## Purpose
Implement dynamic confidence scoring for candidate memories from multi-signal feedback.

## ADDED Requirements

### Requirement: MemoryScorer
`MemoryScorer` SHALL compute confidence 0–20 from:
- Base 5 for proposed.
- +3 per confirming feedback event (cap +6).
- +2 if retrieval usage count > threshold (cap +4).
- +3 if multiple actors agree (cap +3).
- -5 per rejection/flag.
- -3 per contradictory evidence.

Thresholds: ≥14 verified, ≥8 supported, else proposed.

#### Scenario: Confirming feedback raises score
- **WHEN** a candidate has 2 confirming feedback events (+6) and 1 retrieval usage (+2)
- **THEN** score = 5 + 6 + 2 = 13 (supported).

#### Scenario: Rejection drops score
- **WHEN** a candidate with score 12 receives a rejection (-5)
- **THEN** score becomes 7 (proposed, below supported threshold).

### Requirement: Scoring triggers retrieval tier
The system SHALL assign retrieval weight based on state:
- verified → 0.8
- supported → 0.4
- proposed → 0.1

#### Scenario: Retrieval weight
- **WHEN** a candidate is verified
- **THEN** it appears in `text.candidates.*` space with weight 0.8, below authoritative weight 1.0.
