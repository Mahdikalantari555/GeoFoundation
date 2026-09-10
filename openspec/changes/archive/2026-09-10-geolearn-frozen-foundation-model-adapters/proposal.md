## Why

When the online classifier has too few training samples, raw predictions are
unreliable. A nearest-neighbor fallback over the cached OLMoEarth embeddings
provides a reasonable prediction even before the classifier is well-trained.
This bridge ensures GeoLearn is useful from the first interaction, not only
after extensive labeling.

## What Changes

1. Add `FrozenEmbeddingAdapter` class: given an unseen asset, retrieve its
   cached embedding (or request GeoMemory to embed it if absent), find k nearest
   neighbors among labeled cached assets, and return a weighted-vote prediction.
2. The adapter auto-selects between NN fallback and classifier prediction based
   on `n_training_samples` threshold (default: switch to classifier after 30
   labeled samples).
3. Adapters are keyed by `(crop_type, region)` just like classifiers.

## Capabilities

### New Capabilities
- `geolearn-frozen-foundation-model-adapters`: NN fallback over frozen embeddings.

## Impact

- Reuses existing `EmbeddingCache.nn_lookup()` — no new storage.
- Predictions from adapter carry `source="nn_fallback"` flag so agents know
  the confidence basis.
- No new dependencies.
