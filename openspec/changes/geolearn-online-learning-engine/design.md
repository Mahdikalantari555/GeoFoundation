# Design: geolearn-online-learning-engine

Extends geolearn-core-framework with streaming semantics.

## Module layout

```
geolearn/streaming.py     # StreamingWindow
geolearn/drift.py         # SimpleDriftDetector, RiverDriftDetector
geolearn/scheduler.py     # OnlineScheduler
```

## StreamingWindow

FIFO buffer using `collections.deque(maxlen=N)`. `add(item)` appends; `items()` returns list copy. No decay — pure window.

## DriftDetector protocol

Abstract base with `check(new_label, true_label) -> bool`. Two concretizations:
- `SimpleDriftDetector`: tracks last `window` predictions; triggers when error_rate > threshold.
- `RiverDriftDetector`: wraps `river.drift.PageHinkley` when available; falls back to Simple.

The protocol allows swapping drift detectors without changing scheduler logic.

## OnlineScheduler

```python
class OnlineScheduler:
    def __init__(self, batch_size=10, min_interval_s=60):
        self.buffer = []
        self.batch_size = batch_size
        self.min_interval_s = min_interval_s
        self.last_train_time = 0.0

    def maybe_train(self, classifier, embedding_cache, new_samples):
        """Accumulate samples and call classifier.partial_fit when triggered."""
        self.buffer.extend(new_samples)
        now = time.monotonic()
        trigger = (len(self.buffer) >= self.batch_size
                   or (now - self.last_train_time) >= self.min_interval_s)
        if trigger and self.buffer:
            X = np.array([s.embedding for s in self.buffer])
            y = np.array([s.label for s in self.buffer])
            classifier.partial_fit(X, y)
            self.buffer.clear()
            self.last_train_time = now
```

## Integration

Scheduler is injected into `ClassifierStore` at construction time. When absent, `partial_fit` is called directly (backward-compatible).
