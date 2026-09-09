## Why

Embedding vectors themselves are static (OLMoEarth is frozen), but the
**association** between embeddings and labels evolves as more ground-truth
data arrives. Storing embeddings without updating their label context wastes
the opportunity to refine which embeddings are considered "similar." This
change keeps the embedding vectors frozen but maintains a learned mapping
table that improves prediction quality through incremental association updates.

## What Changes

1. Add `AssociationMap` class: a lightweight lookup table mapping
   `(embedding_hash, label) → confidence_score` that is updated via
   `partial_fit()`-equivalent increment on each new labeled sample.
2. On prediction, combine the association map score with the classifier
   probability via a weighted blend (default 0.5/0.5) for improved robustness.
3. Association scores decay over time (exponential forgetting, half-life
   configurable, default 90 days) to prevent stale associations from dominating.

## Capabilities

### New Capabilities
- `geolearn-incremental-embedding-learning`: association map with decay.

## Impact

- Adds ~100 lines to geolearn. Uses existing embedding cache infrastructure.
- No architectural change to classifier pipeline; enhancement layer only.
