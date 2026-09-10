## Why

Individual supervisors and researchers develop personalized modeling
preferences over time — some trust higher thresholds, others prefer aggressive
classification. User-specific adaptation stores these preferences and
adjusts the confidence threshold and classifier behavior per-user, building
on top of region-specific adaptation.

## What Changes

1. Add `UserSettings` Pydantic model: `user_id`, `confidence_threshold` (float,
   default 0.6), `preferred_classifier` (enum, default "sgd"),
   `auto_train_on_feedback` (bool, default True), `updated_at` (ISO timestamp).
2. Persist settings in `geolearn.db` under a `user_settings` table.
3. On prediction, resolve settings by `(user_id, region)` and apply the
   user's threshold override before returning the abstain decision.
4. GeoAgent tool `geo_get_user_settings(user_id?)` and `geo_update_user_settings(partial_settings)`
   expose the contract.

## Capabilities

### New Capabilities
- `geolearn-user-specific-adaptation`: per-user confidence and behavior preferences.

## Impact

- Adds ~60 lines for settings model + persistence.
- Settings are completely optional; missing settings use defaults.
- Backward-compatible with existing profile system.
