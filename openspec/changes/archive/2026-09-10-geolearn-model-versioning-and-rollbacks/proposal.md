## Why

As the classifier learns incrementally, there is no way to revert to a
previous state if a bad batch of feedback corrupts the model. Model
versioning with rollback capability is essential for production trust —
a degraded model should never silently persist across sessions.

## What Changes

1. Add version stamp to every classifier save: `<key>__<version>__<timestamp>.pkl`
   where version is a monotonically increasing integer.
2. Add `list_versions(key) -> list[ModelVersion]` returning version number,
   save timestamp, n_samples, and sha256 of the file.
3. Add `rollback_to(key, version) -> bool` that restores a prior classifier
   state and logs the rollback event.
4. Add `geo_list_model_versions(key?)` and `geo_rollback_model(key, version)`
   tools in GeoAgent.
5. Default retention: keep last 10 versions per key; older versions are
   garbage-collected on next save.

## Capabilities

### New Capabilities
- `geolearn-model-versioning-and-rollbacks`: versioned classifier state with rollback.

## Impact

- File naming convention change: `<key>_<version>_<ts>.pkl`.
- Garbage collection runs automatically on save — no manual cleanup needed.
- Rollback events are logged to a `rollback_history` table in geolearn.db
  for audit purposes.
- No impact on prediction path; versioning is purely operational.
