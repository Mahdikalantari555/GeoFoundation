from typing import Any

import numpy as np

from geolearn.calibration import (
    CalibrationCurve,
    compute_final_confidence,
    prediction_entropy,
)


class ConfidenceModel:
    def __init__(
        self,
        threshold: float = 0.6,
        entropy_threshold: float = 0.8,
        calibration_curve: CalibrationCurve | None = None,
    ) -> None:
        self.threshold = float(threshold)
        self.entropy_threshold = float(entropy_threshold)
        self.calibration_curve = calibration_curve or CalibrationCurve()

    def evaluate(self, probabilities: Any) -> tuple[list[float], bool]:
        prob_arr = np.asarray(probabilities, dtype=np.float64)
        if prob_arr.ndim == 1:
            prob_arr = prob_arr.reshape(1, -1)

        confidences: list[float] = []
        force_abstain = False

        for row in prob_arr:
            raw_max = float(np.max(row))
            cal_p = self.calibration_curve.calibrate(raw_max)
            ent = prediction_entropy(row)
            final_conf = compute_final_confidence(cal_p, ent)
            confidences.append(final_conf)
            if ent > self.entropy_threshold:
                force_abstain = True

        abstain = force_abstain or any(c < self.threshold for c in confidences)
        return confidences, abstain

    def is_abstain(self, confidence: float) -> bool:
        return confidence < self.threshold
