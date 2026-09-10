## Why

GeoLearn v1 provides a frozen-embedding + online-classifier foundation, but
consumers have no way to turn feedback into training signals. Accepted corrections
in GeoMemory's candidate memory sit idle — the classifier never learns from them.
This change wires the feedback→training path:GeoMemory → GeoLearn→`partial_fit()`.

## What Changes

1. Add `geo_train_on_feedback(feedback_ids?, auto_train=True)` tool to GeoAgent.
2. Implement `TrainingPipeline` in geolearn that reads accepted `CandidateMemory`
   entries, extracts embedding+label pairs, and calls `partial_fit()` on the
   appropriate classifier key.
3. Wire candidate memory approval events (from Change 1) to trigger incremental
   updates — optionally batched, not per-event to avoid thrashing.
4. Add `geo_pending_training_count()` tool so the agent can inform users of
   unsynchronized corrections.

## Capabilities

### New Capabilities
- `geolearn-training-pipeline`: Feedback-driven `partial_fit()` loop in geolearn.

### Modified Capabilities
- `core-framework` (geolearn): adds `TrainingPipeline` class.
- `memory-tools` (geoagent): adds `geo_train_on_feedback`, `geo_pending_training_count`.

## Impact

- **New code**: `libs/geolearn/geolearn/training_pipeline.py`; geoagent tool file.
- **Deps**: No new runtime deps. Uses existing geomemory facade for reading
  candidate memory.
- **Risk**: Training cadence must be throttled; uncontrolled `partial_fit()` on
  every feedback event risks catastrophic forgetting. Implementation uses a
  batch window (default: train on every N accepted corrections, or every T minutes).
