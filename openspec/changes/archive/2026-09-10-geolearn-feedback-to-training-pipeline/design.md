# Design: geolearn-feedback-to-training-pipeline

Wires candidate memory corrections into classifier training.

## Data flow

```
GeoMemory candidate_memory table
        ↓ (accepted candidates)
TrainingPipeline.read_pending()
        ↓ (list of (asset_id, label, embedding_hash))
For each (crop_type, region) key:
    Look up embedding from EmbeddingCache
    Build X, y batches
    ClassifierStore.partial_fit_batch(key, X, y, batch_size=10)
        ↓
Update n_training_samples in classifier_state
Log to training_log table
```

## Candidate memory read strategy

Two options considered:
1. **Facade-based**: use `geomemory.candidate_memory.get_accepted()` — cleaner but requires facade export.
2. **Direct SQLite**: query `candidate_memory` table directly with known schema — faster, no facade coupling.

**Decision**: Option 2 for v1 (direct read). The geomemory facade does not currently export candidate retrieval; adding it would be a separate change in geomemory. Direct SQLite read uses the same connection pattern as other libs (isolated connection, WAL-safe).

## Pending tracking

`training_log` table tracks `(key, n_samples, trained_at)` to avoid re-training already-applied feedback. A candidate is "trained" when its asset_id appears in a training_log entry.
