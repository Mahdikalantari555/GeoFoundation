# Design: geolearn-personalization-profiles

Profile storage is a thin SQLite layer on top of geolearn.db.

## Schema

```sql
CREATE TABLE user_profiles (
  user_id       TEXT NOT NULL,
  region        TEXT NOT NULL,
  crop_type     TEXT NOT NULL DEFAULT 'unknown',
  preferred_classifier TEXT NOT NULL DEFAULT 'sgd',
  trained_at    TEXT,
  n_training_samples INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, region)
);
```

## Key resolution order

1. Look up profile for (user_id, region)
2. If found and preferred_classifier != 'sgd', use that classifier type
3. If not found, use default ("unknown", "global") with SGD

## Profile lifecycle

- Created on first access (get_or_create is idempotent)
- Updated implicitly via TrainingPipeline after each partial_fit batch
- Explicit update via geo_update_user_settings tool for manual overrides
