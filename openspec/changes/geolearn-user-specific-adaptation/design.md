# Design: geolearn-user-specific-adaptation

User settings override global defaults but never region-level behavior.

## Priority order (highest to lowest)

1. User-specific confidence_threshold
2. Region-level default (0.6)

## Settings persistence

```sql
CREATE TABLE user_settings (
  user_id             TEXT PRIMARY KEY,
  confidence_threshold REAL NOT NULL DEFAULT 0.6,
  preferred_classifier TEXT NOT NULL DEFAULT 'sgd',
  auto_train_on_feedback BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at          TEXT NOT NULL
);
```

## geo_update_user_settings semantics

Partial update: only fields provided in the request are changed; others retain
their current values. Missing fields are ignored, not set to None.
