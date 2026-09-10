import numpy as np
import pytest
from geolearn.classifier import OnlineClassifier
from geolearn.exceptions import ClassifierNotTrainedError

def test_classifier_fit_predict():
    clf = OnlineClassifier(random_state=42)
    with pytest.raises(ClassifierNotTrainedError):
        clf.predict([[0.1, 0.2]])

    X = np.array([[1.0, 1.0], [-1.0, -1.0], [0.9, 0.8], [-0.8, -0.9]])
    y = np.array([1, 0, 1, 0])
    clf.fit(X, y)

    preds = clf.predict([[0.8, 0.7], [-0.7, -0.8]])
    assert list(preds) == [1, 0]

    probas = clf.predict_proba([[0.8, 0.7]])
    assert probas.shape == (1, 2)
    assert np.allclose(probas.sum(axis=1), 1.0)

def test_classifier_partial_fit_incremental():
    clf = OnlineClassifier()
    X1 = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y1 = np.array([1, 0])
    clf.partial_fit(X1, y1)
    assert clf.classes_ == [0, 1]

    # Subsequent partial_fit without specifying classes
    X2 = np.array([[1.2, 0.9], [-1.1, -0.8]])
    y2 = np.array([1, 0])
    clf.partial_fit(X2, y2)

    pred = clf.predict([[1.0, 1.0]])
    assert pred[0] == 1

def test_classifier_save_load(tmp_path):
    clf = OnlineClassifier()
    X = np.array([[1.0, 0.0], [0.0, 1.0]])
    y = np.array([0, 1])
    clf.fit(X, y)

    save_file = tmp_path / "model.pkl"
    clf.save(save_file)

    loaded = OnlineClassifier.load(save_file)
    assert loaded.is_fitted
    assert list(loaded.predict([[1.0, 0.0]])) == [0]
