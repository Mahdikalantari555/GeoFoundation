## Why

Different regions have different crop types, soil conditions, and stress
patterns. A single global classifier cannot capture local nuance. This change
adds per-region classifier isolation: each `(crop_type, region)` pair gets
its own `SGDClassifier` instance with independent `partial_fit()` history,
so regional expertise accumulates without contamination from unrelated domains.

## What Changes

1. Extend `ClassifierStore` to support hierarchical keys: `(crop_type, region,
   sub_region?)` where sub_region is optional.
2. Add `geo_select_region(crop_type, region) -> classifier_key` tool in geoagent
   so the agent can query which regional classifier is active.
3. Region-level classifiers inherit from parent (crop_type-only) classifiers
   via initial weight transfer on first use, avoiding cold-start from zero.

## Capabilities

### New Capabilities
- `geolearn-region-specific-adaptation`: hierarchical per-region classifier store.

## Impact

- Schema extension: `classifier_state` table gains optional `sub_region` column
  (nullable, backward-compatible).
- Weight transfer is a one-time operation; subsequent updates are independent.
- No breaking changes to existing single-key usage.
