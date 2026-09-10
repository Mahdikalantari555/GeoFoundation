## Why

GeoLearn v1 uses static `partial_fit()` cycles with no concept of data drift or
streaming semantics. Agricultural imagery patterns shift seasonally and across
years — a model trained on spring wheat may degrade on autumn cycles. This
change adds River-style streaming learning: sliding windows, drift detection,
and online hyperparameter adjustment. It is the "River for remote sensing"
layer — but River is an optional `[river]` extra, not a hard dependency.

## What Changes

1. Add `StreamingWindow` class: fixed-size sliding window over embedding+label
   pairs, discarding oldest samples beyond `window_size`.
2. Add `DriftDetector` protocol (optional River integration): detect when
   prediction error rate exceeds a threshold over a rolling window.
3. Add `OnlineScheduler`: schedules `partial_fit()` calls at configurable
   intervals (batch size N or time window T), preventing training thrash.
4. When River is installed (`[river]` extra), use River's `PrequentialEffectiveness`
   and `PageHinkley` for drift detection; otherwise fall back to simple
   accuracy-tracking heuristics.

## Capabilities

### New Capabilities
- `geolearn-online-learning-engine`: streaming window, drift detection, scheduled training.

## Impact

- **Optional dep**: `river>=0.20` only loaded when extra is installed.
- **Backward-compatible**: default scheduler uses simple counter-based batching.
- **Risk**: Drift detection introduces non-determinism in training cadence;
  logged explicitly so thesis metrics can account for it.
