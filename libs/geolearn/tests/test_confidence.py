import pytest
from geolearn.confidence import ConfidenceModel

def test_confidence_threshold_crossing():
    cm = ConfidenceModel(threshold=0.6)
    # [1.0, 0.0] has entropy 0, calibrated 1.0 -> final 1.0 -> not abstain
    confidences, abstain = cm.evaluate([[1.0, 0.0]])
    assert confidences == pytest.approx([1.0])
    assert abstain is False

    # [0.7, 0.3] has positive entropy -> final ~0.525 -> abstain
    confidences, abstain = cm.evaluate([[0.7, 0.3]])
    assert confidences[0] < 0.6
    assert abstain is True

def test_confidence_edge_case():
    cm = ConfidenceModel(threshold=0.6)
    assert cm.is_abstain(0.6) is False
    assert cm.is_abstain(0.599) is True

def test_confidence_multiple_samples():
    cm = ConfidenceModel(threshold=0.6)
    probas = [[1.0, 0.0], [0.5, 0.5], [0.99, 0.01]]
    confidences, abstain = cm.evaluate(probas)
    assert len(confidences) == 3
    assert confidences[0] > 0.9
    assert confidences[1] < 0.5
    assert abstain is True  # because second sample is < 0.6
