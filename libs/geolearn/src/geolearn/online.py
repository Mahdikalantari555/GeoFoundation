from __future__ import annotations

import time
from collections import deque
from typing import Any, Generic, Protocol, TypeVar

import numpy as np

try:
    from river.drift import PageHinkley

    HAS_RIVER = True
except ImportError:
    HAS_RIVER = False
    PageHinkley = None

T = TypeVar("T")


class StreamingWindow(Generic[T]):
    """Fixed-size FIFO sliding window discarding oldest elements beyond max_size."""

    def __init__(self, max_size: int = 100) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        self.max_size = int(max_size)
        self._buffer: deque[T] = deque(maxlen=self.max_size)

    def add(self, item_or_embedding: Any, label: Any = None) -> None:
        """Add an item or (embedding, label) pair to the window."""
        if label is not None:
            self._buffer.append((item_or_embedding, label))  # type: ignore[arg-type]
        else:
            self._buffer.append(item_or_embedding)

    def append(self, item_or_embedding: Any, label: Any = None) -> None:
        self.add(item_or_embedding, label=label)

    def items(self) -> list[T]:
        """Return all items in insertion order."""
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def __iter__(self) -> Any:
        return iter(self._buffer)


class DriftDetector(Protocol):
    def check(self, y_pred: Any, y_true: Any = None) -> bool: ...


class SimpleDriftDetector:
    """Sliding-window drift detector tracking prediction error rate."""

    def __init__(
        self,
        error_rate_threshold: float = 0.3,
        window: int = 50,
    ) -> None:
        if window <= 0:
            raise ValueError(f"window must be positive, got {window}")
        self.error_rate_threshold = float(error_rate_threshold)
        self.window = int(window)
        self._history: deque[int] = deque(maxlen=self.window)
        self.detected: bool = False

    @property
    def error_rate(self) -> float:
        if not self._history:
            return 0.0
        return sum(self._history) / len(self._history)

    def check(self, y_pred: Any, y_true: Any = None) -> bool:
        """Record sample outcome and return whether drift is detected."""
        if y_true is None and isinstance(y_pred, (bool, int, float)):
            is_error = 1 if y_pred else 0
        else:
            is_error = 1 if y_pred != y_true else 0

        self._history.append(is_error)
        self.detected = self.error_rate > self.error_rate_threshold
        return self.detected

    def reset(self) -> None:
        self._history.clear()
        self.detected = False


class RiverDriftDetector:
    """Delegates to River's PageHinkley if river is installed; falls back to SimpleDriftDetector."""

    def __init__(
        self,
        error_rate_threshold: float = 0.3,
        window: int = 50,
        **river_kwargs: Any,
    ) -> None:
        self.error_rate_threshold = float(error_rate_threshold)
        self.window = int(window)
        self.using_river: bool = bool(HAS_RIVER and PageHinkley is not None)
        self.detected: bool = False

        if self.using_river:
            self._river_detector: Any = PageHinkley(**river_kwargs)
            self._fallback: SimpleDriftDetector | None = None
        else:
            self._river_detector = None
            self._fallback = SimpleDriftDetector(
                error_rate_threshold=self.error_rate_threshold,
                window=self.window,
            )

    def check(self, y_pred: Any, y_true: Any = None) -> bool:
        if self._river_detector is not None:
            if y_true is None and isinstance(y_pred, (bool, int, float)):
                val = float(y_pred)
            else:
                val = 1.0 if y_pred != y_true else 0.0
            self._river_detector.update(val)
            self.detected = bool(self._river_detector.drift_detected)
            return self.detected
        elif self._fallback is not None:
            self.detected = self._fallback.check(y_pred, y_true)
            return self.detected
        return False

    def reset(self) -> None:
        self.detected = False
        if self._river_detector is not None and hasattr(self._river_detector, "_reset"):
            self._river_detector._reset()
        if self._fallback is not None:
            self._fallback.reset()


class OnlineScheduler:
    """Accumulates samples and triggers partial_fit on batch size or time elapsed."""

    def __init__(
        self,
        batch_size: int = 10,
        min_interval_s: float = 60.0,
        drift_detector: DriftDetector | None = None,
    ) -> None:
        self.batch_size = int(batch_size)
        self.min_interval_s = float(min_interval_s)
        self.drift_detector = drift_detector
        self.buffer: list[tuple[np.ndarray, int]] = []
        self.last_train_time: float = 0.0
        self.last_trained_count: int = 0

    def add(self, embedding: Any, label: int) -> None:
        arr = np.asarray(embedding, dtype=np.float32)
        self.buffer.append((arr, int(label)))

    def should_train(self, current_time: float | None = None) -> bool:
        if not self.buffer:
            return False
        if self.drift_detector is not None and getattr(self.drift_detector, "detected", False):
            return False
        now = current_time if current_time is not None else time.monotonic()
        batch_ready = len(self.buffer) >= self.batch_size
        time_ready = self.last_train_time > 0.0 and (now - self.last_train_time) >= self.min_interval_s
        return batch_ready or time_ready

    def maybe_train(
        self,
        classifier: Any,
        embedding_cache: Any = None,
        new_samples: list[Any] | None = None,
        current_time: float | None = None,
    ) -> bool:
        """Accumulate new samples and call classifier.partial_fit when triggered."""
        if new_samples:
            for s in new_samples:
                if isinstance(s, tuple) and len(s) == 2:
                    self.add(s[0], s[1])
                elif hasattr(s, "embedding") and hasattr(s, "label"):
                    self.add(s.embedding, s.label)
                elif isinstance(s, dict) and "embedding" in s and "label" in s:
                    self.add(s["embedding"], s["label"])

        now = current_time if current_time is not None else time.monotonic()
        if self.last_train_time == 0.0:
            self.last_train_time = now

        if self.drift_detector is not None and getattr(self.drift_detector, "detected", False):
            return False

        batch_trigger = len(self.buffer) >= self.batch_size
        time_trigger = bool(self.buffer and (now - self.last_train_time) >= self.min_interval_s)

        if (batch_trigger or time_trigger) and self.buffer:
            count = len(self.buffer)
            X = np.asarray([s[0] for s in self.buffer], dtype=np.float32)
            y = np.asarray([s[1] for s in self.buffer], dtype=np.int64)
            classifier.partial_fit(X, y)
            self.buffer.clear()
            self.last_train_time = now
            self.last_trained_count = count
            return True
        return False

    def step(
        self,
        classifier: Any,
        new_samples: list[Any] | None = None,
        current_time: float | None = None,
        force: bool = False,
    ) -> bool:
        """Step scheduler, optionally forcing partial_fit on current buffer."""
        if force and self.buffer:
            now = current_time if current_time is not None else time.monotonic()
            count = len(self.buffer)
            X = np.asarray([s[0] for s in self.buffer], dtype=np.float32)
            y = np.asarray([s[1] for s in self.buffer], dtype=np.int64)
            classifier.partial_fit(X, y)
            self.buffer.clear()
            self.last_train_time = now
            self.last_trained_count = count
            return True
        return self.maybe_train(classifier, new_samples=new_samples, current_time=current_time)

    def flush(self, classifier: Any, current_time: float | None = None) -> bool:
        """Force flush buffer into classifier.partial_fit."""
        return self.step(classifier, current_time=current_time, force=True)
