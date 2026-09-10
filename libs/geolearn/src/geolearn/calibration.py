from collections import deque
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


def prediction_entropy(proba_array: Any) -> float:
    """Compute prediction entropy -sum(p * log(p)) in natural units."""
    arr = np.asarray(proba_array, dtype=np.float64)
    if arr.size <= 1:
        return 0.0
    arr = arr[arr > 0]
    if len(arr) == 0:
        return 0.0
    return float(-np.sum(arr * np.log(arr)))


def compute_final_confidence(calibrated_proba: float, entropy: float) -> float:
    """Blend calibrated probability with entropy penalty."""
    log2 = float(np.log(2.0))
    entropy_norm = min(max(entropy / log2, 0.0), 1.0)
    final = 0.7 * float(calibrated_proba) + 0.3 * (1.0 - entropy_norm)
    return float(np.clip(final, 0.0, 1.0))


class CalibrationCurve:
    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self.buffer: deque[tuple[float, int]] = deque(maxlen=window_size)
        self.model: IsotonicRegression | None = None

    def add_observation(self, predicted_proba: float, is_correct: int | bool) -> None:
        self.buffer.append((float(predicted_proba), int(is_correct)))
        if len(self.buffer) >= 10:
            self.fit()

    def fit(self) -> "CalibrationCurve":
        if len(self.buffer) < 10:
            return self
        X = np.array([x[0] for x in self.buffer], dtype=np.float64)
        y = np.array([x[1] for x in self.buffer], dtype=np.float64)
        self.model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.model.fit(X, y)
        return self

    def calibrate(self, proba: float) -> float:
        if self.model is None or len(self.buffer) < 10:
            return float(proba)
        pred = self.model.predict([float(proba)])[0]
        return float(np.clip(pred, 0.0, 1.0))
