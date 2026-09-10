import math
import numpy as np
import pytest
from geolearn.calibration import CalibrationCurve, compute_final_confidence, prediction_entropy
from geolearn.confidence import ConfidenceModel

def test_prediction_entropy_bounds():
    assert prediction_entropy([1.0, 0.0, 0.0]) == 0.0
    ent = prediction_entropy([0.33, 0.33, 0.34])
    assert abs(ent - 1.098) < 0.01

def test_compute_final_confidence():
    # When entropy is 0, score is 0.7 * proba + 0.3
    res = compute_final_confidence(1.0, 0.0)
    assert pytest.approx(res) == 1.0

    # Low calibrated proba, high entropy
    res2 = compute_final_confidence(0.5, 1.0)
    assert res2 < 0.5

def test_calibration_curve_insufficient_data():
    cc = CalibrationCurve()
    assert cc.calibrate(0.55) == 0.55

def test_calibration_curve_fit():
    cc = CalibrationCurve()
    for _ in range(10):
        cc.add_observation(0.55, 1)
    cal = cc.calibrate(0.55)
    assert cal > 0.55  # upward adjustment

def test_entropy_based_abstention():
    # proba = [0.4, 0.35, 0.25] -> entropy > 0.8 bits
    cm = ConfidenceModel(threshold=0.6, entropy_threshold=0.8)
    confidences, abstain = cm.evaluate([[0.4, 0.35, 0.25]])
    assert abstain is True
