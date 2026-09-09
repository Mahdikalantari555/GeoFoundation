# geolearn-incremental-embedding-learning — Specification (v0.2)

Maintains an association map between embedding hashes and labels with
exponential decay, improving prediction robustness beyond raw classifier output.

## Requirements

### Requirement: AssociationMap
`AssociationMap(half_life_days=90)` SHALL maintain a dict mapping
`(embedding_hash, label) -> score`. On each new labeled sample:
1. Compute hash of the embedding (SHA-256 of serialized bytes).
2. Increment score for `(hash, label)` pair by 1.
3. Apply exponential decay to ALL scores: `score *= exp(-dt / half_life_days)`.
4. Prune scores below 0.01.

#### Scenario: Score decay
- **WHEN** 90 days pass with no new training
- **THEN** all association scores are halved

#### Scenario: New sample reinforces association
- **WHEN** a sample with hash H and label L arrives, and (H,L) already has score 5
- **THEN** new score is 6 (before next decay cycle)

### Requirement: Blended prediction
`AssociationMap.blend(classifier_proba, embedding, key) -> calibrated_proba`
SHALL combine classifier probability with association-map vote (weighted 50/50)
and return the blended result.

### Requirement: Transparent integration
Callers see no difference — `OnlineClassifier.predict()` internally applies
the blend when an association map exists for the requested key.

## Non-goals

- Caching full embedding vectors (only hashes stored in association map)
- Pre-computing all pairwise associations
