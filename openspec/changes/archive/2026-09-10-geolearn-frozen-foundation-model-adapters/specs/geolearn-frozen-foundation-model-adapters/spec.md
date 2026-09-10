# geolearn-frozen-foundation-model-adapters — Specification (v0.2)

Adds a nearest-neighbor fallback over frozen OLMoEarth embeddings for cases
where the online classifier lacks sufficient training data.

## Requirements

### Requirement: FrozenEmbeddingAdapter
`FrozenEmbeddingAdapter(cache: EmbeddingCache, k: int = 5)` SHALL implement:
- `predict(embedding, key) -> PredictionResult` — find k nearest labeled
  neighbors, return weighted-vote prediction with confidence based on vote
  distribution entropy.

#### Scenario:NN fallback used
- **WHEN** classifier has fewer than 30 training samples and `predict()` is called
- **THEN** result includes `source="nn_fallback"` and confidence derived from
  neighbor vote distribution

#### Scenario: Classifier takes over
- **WHEN** classifier has ≥ 30 training samples
- **THEN** the adapter delegates to the classifier and sets `source="classifier"`

### Requirement: Integration with ClassifierStore
`ClassifierStore.predict()` SHALL auto-select between adapter and classifier
based on `n_training_samples >= 30` threshold. This is transparent to callers.

### Requirement: No new storage
The adapter reuses `EmbeddingCache` exclusively; no separate storage is created.

## Non-goals

- Embedding regeneration or fine-tuning
- Cross-modal embedding mixing
- Deep metric learning
