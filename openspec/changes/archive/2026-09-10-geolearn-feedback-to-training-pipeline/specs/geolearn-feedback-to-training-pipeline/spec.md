# geolearn-feedback-to-training-pipeline — Specification (v0.2)

Wires GeoMemory's candidate memory corrections into GeoLearn's `partial_fit()` cycle.

## Requirements

### Requirement: TrainingPipeline class
`TrainingPipeline(geolearn_dir, geomemory_workspace)` SHALL:
1. Read accepted candidate memory entries from GeoMemory's `candidate_memory` table
   (via public facade or direct SQLite read — see decision below).
2. Group them by `(crop_type, region)` key.
3. Call `classifier.partial_fit(embeddings, labels)` in batches per key.
4. Update `ClassifierStore.n_training_samples` after each batch.
5. Log training events to a `training_log` table.

#### Scenario: Batch training on accepted feedback
- **WHEN** 15 new accepted candidates exist across 2 keys
- **THEN** two `partial_fit()` calls are made (one per key), each with up to 10 samples
  (batch_size default)

#### Scenario: No pending feedback
- **WHEN** all candidates are already trained
- **THEN** training log records zero new samples; no classifier call is made

### Requirement: Integration point with GeoMemory
The pipeline reads candidate memory via the GeoMemory public facade when available;
if not, it reads directly from the SQLite `candidate_memory` table. This is
documented as a controlled coupling (not a full facade dependency).

### Requirement: geo_train_on_feedback tool
GeoAgent tool SHALL accept optional `feedback_ids` list. When omitted, all
pending (untrained) accepted candidates are processed. Returns
`{"key": str, "samples_trained": int, "total_n_samples": int}` per key.

### Requirement: geo_pending_training_count tool
Returns `{"total_pending": int, "by_key": {key: count}}` — how many accepted
candidates are waiting for training.

## Non-goals

- Automatic training on every feedback event (batching required)
- Retraining from scratch
- Cross-key sample sharing
