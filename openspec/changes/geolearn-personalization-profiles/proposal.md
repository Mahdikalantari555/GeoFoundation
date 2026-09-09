## Why

A classifier trained on Khuzestan sugarcane should not be applied to Fars rice
without adaptation. Per-region and per-user personalization is the core value
proposition of GeoLearn. This change adds persistent profile storage so that
classifiers learned in one session carry over to the next, keyed by user and
region.

## What Changes

1. Add `UserProfile` Pydantic model: `user_id`, `region`, `crop_type`,
   `preferred_classifier`, `trained_at`, `n_training_samples`.
2. Add `ProfileStore` (SQLite, inside `geolearn.db`) that maps `(user_id, region)`
   → `UserProfile` with persistence across sessions.
3. Extend `ClassifierStore` to look up profiles before selecting a classifier key.
4. Auto-create a default profile for anonymous users (`user_id="anonymous"`).

## Capabilities

### New Capabilities
- `geolearn-personalization-profiles`: user+region profile persistence and lookup.

## Impact

- Adds `profile_store.py` (~80 lines) + migration entry in schema.
- No breaking changes to existing API.
- Profiles are optional; missing profile falls back to global classifier.
