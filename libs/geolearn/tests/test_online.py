from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from geolearn.classifier import OnlineClassifier
from geolearn.online import (
    OnlineScheduler,
    RiverDriftDetector,
    SimpleDriftDetector,
    StreamingWindow,
)
from geolearn.persistence import ClassifierStore


def test_streaming_window_basic_operations():
    window: StreamingWindow[tuple[list[float], int]] = StreamingWindow(max_size=5)
    assert len(window) == 0

    window.add([1.0, 2.0], 1)
    window.add(([3.0, 4.0], 0))
    assert len(window) == 2

    items = window.items()
    assert len(items) == 2
    assert items[0] == ([1.0, 2.0], 1)
    assert items[1] == ([3.0, 4.0], 0)

    window.clear()
    assert len(window) == 0


def test_streaming_window_overflow():
    window: StreamingWindow[int] = StreamingWindow(max_size=100)
    for i in range(105):
        window.add(i)

    assert len(window) == 100
    items = window.items()
    assert items[0] == 5
    assert items[-1] == 104


def test_streaming_window_invalid_size():
    with pytest.raises(ValueError):
        StreamingWindow(max_size=0)


def test_simple_drift_detector_normal_and_exact_boundary():
    detector = SimpleDriftDetector(error_rate_threshold=0.3, window=50)

    # 35 correct predictions
    for _ in range(35):
        assert detector.check(1, 1) is False

    # 15 wrong predictions: total 15 errors in 50 -> error_rate = 0.30 -> exactly at threshold (not > 0.3)
    for _ in range(15):
        res = detector.check(0, 1)
    assert res is False
    assert pytest.approx(detector.error_rate, rel=1e-5) == 0.30
    assert detector.detected is False

    # 1 more wrong prediction replaces a correct one: 16 errors in 50 -> error_rate = 0.32 > 0.30 -> True
    triggered = detector.check(0, 1)
    assert triggered is True
    assert detector.detected is True
    assert pytest.approx(detector.error_rate, rel=1e-5) == 0.32

    # Reset
    detector.reset()
    assert detector.detected is False
    assert detector.error_rate == 0.0


def test_river_drift_detector_fallback():
    # In environment without river, RiverDriftDetector falls back gracefully
    detector = RiverDriftDetector(error_rate_threshold=0.3, window=50)
    for _ in range(10):
        detector.check(1, 1)
    assert detector.detected is False

    for _ in range(25):
        detector.check(0, 1)
    assert detector.detected is True

    detector.reset()
    assert detector.detected is False


def test_river_drift_detector_mocked_river():
    mock_ph_class = MagicMock()
    mock_ph_inst = MagicMock()
    mock_ph_inst.drift_detected = True
    mock_ph_class.return_value = mock_ph_inst

    with patch("geolearn.online.HAS_RIVER", True), patch(
        "geolearn.online.PageHinkley", mock_ph_class
    ):
        detector = RiverDriftDetector(error_rate_threshold=0.3, window=50)
        assert detector.using_river is True
        res = detector.check(0, 1)
        assert res is True
        mock_ph_inst.update.assert_called_with(1.0)


def test_online_scheduler_batch_trigger():
    clf = OnlineClassifier()
    scheduler = OnlineScheduler(batch_size=10, min_interval_s=60.0)

    # Add 9 samples at t=10.0 -> no trigger
    samples_9 = [([float(i), float(i)], i % 2) for i in range(9)]
    triggered = scheduler.maybe_train(clf, new_samples=samples_9, current_time=10.0)
    assert triggered is False
    assert len(scheduler.buffer) == 9
    assert not clf.is_fitted

    # Add 1 more sample at t=11.0 (within 1s) -> triggers batch fit
    sample_10 = [([9.0, 9.0], 1)]
    triggered = scheduler.maybe_train(clf, new_samples=sample_10, current_time=11.0)
    assert triggered is True
    assert len(scheduler.buffer) == 0
    assert clf.is_fitted


def test_online_scheduler_time_trigger():
    clf = OnlineClassifier()
    scheduler = OnlineScheduler(batch_size=10, min_interval_s=60.0)

    # 3 samples arrive at t=100.0
    samples_3 = [([1.0, 2.0], 1), ([3.0, 4.0], 0), ([5.0, 6.0], 1)]
    scheduler.maybe_train(clf, new_samples=samples_3, current_time=100.0)
    assert not clf.is_fitted
    assert len(scheduler.buffer) == 3

    # At t=150.0 (50s passed < 60s) -> no trigger
    assert scheduler.maybe_train(clf, current_time=150.0) is False
    assert not clf.is_fitted

    # At t=161.0 (61s passed >= 60s) -> triggers partial_fit
    assert scheduler.maybe_train(clf, current_time=161.0) is True
    assert clf.is_fitted
    assert len(scheduler.buffer) == 0


def test_online_scheduler_pauses_on_drift():
    drift = SimpleDriftDetector(error_rate_threshold=0.3, window=10)
    for _ in range(5):
        drift.check(0, 1)  # 5 errors in 5 samples = 100% > 30%
    assert drift.detected is True

    scheduler = OnlineScheduler(batch_size=5, min_interval_s=60.0, drift_detector=drift)
    samples = [([1.0, 1.0], 1)] * 10
    clf = OnlineClassifier()

    # Even with 10 samples (>= batch_size 5), training is paused due to drift
    assert scheduler.maybe_train(clf, new_samples=samples) is False
    assert not clf.is_fitted


def test_online_scheduler_classifier_store_integration(tmp_path):
    scheduler = OnlineScheduler(batch_size=5, min_interval_s=60.0)
    store = ClassifierStore(tmp_path, scheduler=scheduler)
    key = ("wheat", "khuzestan")

    # Initial classifier not fitted
    clf = store.get_classifier(key)
    assert not clf.is_fitted

    # Add 4 samples through store -> buffer holds 4, not yet saved/trained
    X_4 = np.array([[1.0, 1.0], [1.1, 1.0], [0.9, 1.2], [1.0, 0.8]])
    y_4 = np.array([1, 1, 1, 1])
    store.partial_fit(key, X_4, y_4, classes=[0, 1])
    assert store.get_n_samples(key) == 0

    # Add 1 more sample -> batch size 5 reached, training triggers
    X_1 = np.array([[0.0, 0.0]])
    y_1 = np.array([0])
    store.partial_fit(key, X_1, y_1)
    assert store.get_n_samples(key) == 5

    loaded_clf = store.get_classifier(key)
    assert loaded_clf.is_fitted
