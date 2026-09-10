# geolearn-online-learning-engine — Specification (v0.2)

Extends geolearn-core-framework with streaming semantics: sliding windows,
drift detection, and scheduled training cycles. River is optional (`[river]` extra).

## Requirements

### Requirement: StreamingWindow
`StreamingWindow(max_size)` SHALL maintain a FIFO buffer of `(embedding, label)`
pairs. When `add()` exceeds `max_size`, the oldest pair is discarded. `items()`
returns all pairs in insertion order.

#### Scenario: Window overflow
- **WHEN** max_size=100 and 105 items are added
- **THEN** exactly 100 items remain (oldest 5 discarded)

### Requirement: DriftDetector protocol
`DriftDetector` SHALL expose `check(new_label, old_label) -> bool` where `True`
means drift detected. Two implementations ship:
- `SimpleDriftDetector(error_rate_threshold=0.3, window=50)`: triggers when
  error rate over the last 50 samples exceeds 30%.
- `RiverDriftDetector`: delegates to River's `PageHinkley` when `[river]` is
  installed; falls back to `SimpleDriftDetector` otherwise.

#### Scenario: Drift triggers
- **WHEN** 20 consecutive wrong predictions occur in a 50-sample window
- **THEN** `check()` returns True and the scheduler pauses training

### Requirement: OnlineScheduler
`OnlineScheduler(batch_size=10, min_interval_s=60)` SHALL accumulate training
samples and only call `classifier.partial_fit()` when either `batch_size` samples
are collected OR `min_interval_s` seconds have elapsed since the last train call.

#### Scenario: Batch trigger
- **WHEN** 10 feedback events arrive within 1 second
- **THEN** one `partial_fit()` call is made (not 10)

#### Scenario: Time trigger
- **WHEN** 3 feedback events arrive but 61 seconds pass
- **THEN** `partial_fit()` is called once with those 3 samples

### Requirement: Graceful degradation
When River is not installed, the engine uses `SimpleDriftDetector` and the
scheduler without any ImportError. The `[river]` extra is explicitly optional.

## Non-goals

- Adaptive learning rate tuning
- Multi-window strategies
- Online hyperparameter optimization
