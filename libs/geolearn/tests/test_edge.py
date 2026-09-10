import sys
import numpy as np
import pytest

from geolearn.classifier import OnlineClassifier
from geolearn.edge import EdgeLoader, export_edge_model
from geolearn.exceptions import ClassifierNotTrainedError


def test_export_unfitted_raises(tmp_path):
    clf = OnlineClassifier()
    out_dir = tmp_path / "edge_export"
    with pytest.raises(ClassifierNotTrainedError):
        clf.export_for_edge(out_dir)


def test_edge_export_and_loader_binary(tmp_path):
    clf = OnlineClassifier(random_state=42)
    X = np.array(
        [[1.0, 2.0], [2.0, 3.0], [3.0, 1.0], [-1.0, -2.0], [-2.0, -1.0]],
        dtype=np.float32,
    )
    y = np.array([1, 1, 1, 0, 0])
    clf.fit(X, y)

    out_dir = tmp_path / "edge_binary"
    res = clf.export_for_edge(out_dir)

    assert res["status"] == "exported"
    assert (out_dir / "classifier.json").exists()
    assert (out_dir / "weights.npy").exists()
    assert (out_dir / "intercept.npy").exists()
    assert (out_dir / "manifest.txt").exists()
    assert (out_dir / "README.md").exists()

    loader = EdgeLoader(out_dir)
    assert loader.n_classes == 2
    assert loader.n_features == 2
    assert loader.classes == [0, 1]
    assert "GeoLearn Edge Model Manifest" in loader.manifest

    # Check predictions match exactly
    orig_preds = clf.predict(X)
    edge_preds = loader.predict(X)
    assert list(orig_preds) == list(edge_preds)

    # Check 1D single-sample prediction
    single_pred = loader.predict(X[0])
    assert single_pred == [int(orig_preds[0])]

    # Check probabilities match within float tolerance
    orig_proba = clf.predict_proba(X)
    edge_proba = loader.predict_proba(X)
    assert np.allclose(edge_proba, orig_proba, atol=1e-5)


def test_edge_export_and_loader_multiclass(tmp_path):
    clf = OnlineClassifier(random_state=42)
    X = np.array(
        [
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 1.0],
            [-1.0, -2.0, 0.0],
            [-2.0, -1.0, -1.0],
            [0.0, 0.0, 2.0],
            [0.5, 0.5, 1.5],
        ],
        dtype=np.float32,
    )
    y = np.array([0, 0, 1, 1, 2, 2])
    clf.fit(X, y)

    out_dir = tmp_path / "edge_multi"
    export_edge_model(clf, out_dir)

    loader = EdgeLoader(out_dir)
    assert loader.n_classes == 3
    assert loader.n_features == 3
    assert loader.classes == [0, 1, 2]

    # Compare predictions
    orig_preds = clf.predict(X)
    edge_preds = loader.predict(X)
    assert list(orig_preds) == list(edge_preds)

    orig_proba = clf.predict_proba(X)
    edge_proba = loader.predict_proba(X)
    assert np.allclose(edge_proba, orig_proba, atol=1e-5)


def test_edge_loader_zero_sklearn_dependency(tmp_path, monkeypatch):
    clf = OnlineClassifier(random_state=42)
    X = np.array([[1.0, 2.0], [-1.0, -2.0]], dtype=np.float32)
    y = np.array([1, 0])
    clf.fit(X, y)

    out_dir = tmp_path / "edge_isolated"
    clf.export_for_edge(out_dir)

    # Block scikit-learn from being imported
    monkeypatch.setitem(sys.modules, "sklearn", None)
    monkeypatch.setitem(sys.modules, "sklearn.linear_model", None)

    loader = EdgeLoader(out_dir)
    preds = loader.predict(X)
    assert preds == [1, 0]
    probas = loader.predict_proba(X)
    assert len(probas) == 2
    assert len(probas[0]) == 2
