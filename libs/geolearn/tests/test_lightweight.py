from __future__ import annotations

import pickle
from typing import Any

import numpy as np
import pytest
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import PassiveAggressiveClassifier, SGDClassifier

from geolearn.classifier import ClassifierChoice, OnlineClassifier
from geolearn.exceptions import ClassifierNotTrainedError


def test_classifier_choice_enum() -> None:
    assert ClassifierChoice.SGD == "sgd"
    assert ClassifierChoice.PASSIVE_AGGRESSIVE == "passive_aggressive"
    assert ClassifierChoice.INCREMENTAL_KMEANS == "incremental_kmeans"
    assert isinstance(ClassifierChoice.SGD, str)
    assert ClassifierChoice("sgd") == ClassifierChoice.SGD
    assert ClassifierChoice("passive_aggressive") == ClassifierChoice.PASSIVE_AGGRESSIVE
    assert ClassifierChoice("incremental_kmeans") == ClassifierChoice.INCREMENTAL_KMEANS


def test_default_choice_is_sgd() -> None:
    clf = OnlineClassifier()
    assert clf.choice == ClassifierChoice.SGD
    assert isinstance(clf.clf, SGDClassifier)
    assert clf.n_samples_ == 0
    assert not clf.is_fitted


def test_invalid_choice_raises() -> None:
    with pytest.raises(ValueError):
        OnlineClassifier(choice="unsupported_model")  # type: ignore[arg-type]


def test_unfitted_raises() -> None:
    for choice in ClassifierChoice:
        clf = OnlineClassifier(choice=choice)
        with pytest.raises(ClassifierNotTrainedError):
            clf.predict([[0.0, 0.0]])
        with pytest.raises(ClassifierNotTrainedError):
            clf.predict_proba([[0.0, 0.0]])


def test_sgd_lifecycle(tmp_path: Any) -> None:
    clf = OnlineClassifier(choice=ClassifierChoice.SGD, random_state=42)
    X1 = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y1 = np.array([1, 0])
    clf.partial_fit(X1, y1)

    assert clf.is_fitted
    assert clf.n_samples_ == 2
    assert clf.classes_ == [0, 1]

    X2 = np.array([[1.5, 1.2], [-1.2, -1.5]])
    y2 = np.array([1, 0])
    clf.partial_fit(X2, y2)
    assert clf.n_samples_ == 4

    preds = clf.predict([[1.0, 1.0], [-1.0, -1.0]])
    assert list(preds) == [1, 0]

    probas = clf.predict_proba([[1.0, 1.0], [-1.0, -1.0]])
    assert probas.shape == (2, 2)
    assert np.allclose(probas.sum(axis=1), 1.0)
    assert probas[0, 1] > probas[0, 0]
    assert probas[1, 0] > probas[1, 1]

    save_path = tmp_path / "sgd.pkl"
    clf.save(save_path)
    loaded = OnlineClassifier.load(save_path)
    assert loaded.choice == ClassifierChoice.SGD
    assert loaded.is_fitted
    assert loaded.n_samples_ == 4
    np.testing.assert_array_equal(loaded.predict([[1.0, 1.0]]), preds[:1])


def test_passive_aggressive_lifecycle(tmp_path: Any) -> None:
    clf = OnlineClassifier(
        choice=ClassifierChoice.PASSIVE_AGGRESSIVE, random_state=42
    )
    assert isinstance(clf.clf, PassiveAggressiveClassifier)
    assert clf.clf.C == 1.0
    assert clf.clf.max_iter == 1000
    assert clf.clf.tol == 1e-3

    X1 = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y1 = np.array([1, 0])
    clf.partial_fit(X1, y1)

    assert clf.is_fitted
    assert clf.n_samples_ == 2
    assert clf.classes_ == [0, 1]

    X2 = np.array([[1.2, 0.9], [-0.9, -1.1]])
    y2 = np.array([1, 0])
    clf.partial_fit(X2, y2)
    assert clf.n_samples_ == 4

    test_X = np.array([[1.5, 1.2], [-1.2, -1.5]])
    preds = clf.predict(test_X)
    assert list(preds) == [1, 0]

    probas = clf.predict_proba(test_X)
    assert probas.shape == (2, 2)
    assert np.allclose(probas.sum(axis=1), 1.0)
    assert np.all((probas >= 0.0) & (probas <= 1.0))
    assert probas[0, 1] > probas[0, 0]
    assert probas[1, 0] > probas[1, 1]

    save_path = tmp_path / "pa.pkl"
    clf.save(save_path)
    loaded = OnlineClassifier.load(save_path)
    assert loaded.choice == ClassifierChoice.PASSIVE_AGGRESSIVE
    assert loaded.is_fitted
    assert loaded.n_samples_ == 4
    np.testing.assert_array_equal(loaded.predict(test_X), preds)
    np.testing.assert_allclose(loaded.predict_proba(test_X), probas)


def test_passive_aggressive_multiclass() -> None:
    clf = OnlineClassifier(
        choice="passive_aggressive", random_state=42
    )
    X = np.array([[2.0, 0.0], [-2.0, 0.0], [0.0, 2.0]])
    y = np.array([0, 1, 2])
    clf.fit(X, y)

    assert clf.classes_ == [0, 1, 2]
    probas = clf.predict_proba(X)
    assert probas.shape == (3, 3)
    assert np.allclose(probas.sum(axis=1), 1.0)
    assert np.all((probas >= 0.0) & (probas <= 1.0))
    preds = clf.predict(X)
    np.testing.assert_array_equal(preds, [0, 1, 2])


def test_passive_aggressive_noisy_label_robustness() -> None:
    rng = np.random.RandomState(42)
    X_clean = rng.randn(200, 4)
    y_true = (X_clean[:, 0] + X_clean[:, 1] > 0).astype(int)

    # Inject 30% label noise into training labels
    y_noisy = y_true.copy()
    noise_idx = rng.choice(len(y_noisy), size=int(0.30 * len(y_noisy)), replace=False)
    y_noisy[noise_idx] = 1 - y_noisy[noise_idx]

    # Clean test set
    X_test = rng.randn(100, 4)
    y_test = (X_test[:, 0] + X_test[:, 1] > 0).astype(int)

    pa = OnlineClassifier(choice=ClassifierChoice.PASSIVE_AGGRESSIVE, random_state=42)
    pa.fit(X_clean[:100], y_noisy[:100])
    pa_preds = pa.predict(X_test)
    pa_err = np.mean(pa_preds != y_test)

    sgd = OnlineClassifier(choice=ClassifierChoice.SGD, random_state=42)
    sgd.fit(X_clean[:100], y_noisy[:100])
    sgd_preds = sgd.predict(X_test)
    sgd_err = np.mean(sgd_preds != y_test)

    # Passive aggressive tolerates noisy labels better than SGD
    assert pa_err < sgd_err


def test_incremental_kmeans_unlabeled_lifecycle(tmp_path: Any) -> None:
    clf = OnlineClassifier(
        choice=ClassifierChoice.INCREMENTAL_KMEANS,
        n_clusters=2,
        random_state=42,
    )
    assert isinstance(clf.clf, MiniBatchKMeans)
    assert clf.clf.n_clusters == 2

    # Unlabeled data (y=None)
    X1 = np.array([[5.0, 5.0], [5.1, 4.9], [-5.0, -5.0], [-4.9, -5.1]])
    clf.partial_fit(X1, y=None)
    assert clf.is_fitted
    assert clf.n_samples_ == 4
    assert clf.classes_ == [0, 1]

    # Additional batch
    X2 = np.array([[5.2, 5.0], [-5.1, -4.8]])
    clf.partial_fit(X2)
    assert clf.n_samples_ == 6

    # Predict cluster labels
    preds = clf.predict([[5.0, 5.0], [-5.0, -5.0]])
    assert preds.shape == (2,)
    assert preds[0] != preds[1]  # Assigned to separate clusters

    # Predict pseudo-probabilities from normalized inverse distances
    probas = clf.predict_proba([[5.0, 5.0], [-5.0, -5.0]])
    assert probas.shape == (2, 2)
    assert np.allclose(probas.sum(axis=1), 1.0)
    assert np.all((probas >= 0.0) & (probas <= 1.0))
    # Point exactly at (5, 5) should have high probability for its assigned cluster
    assert probas[0, preds[0]] > 0.9

    # Persistence
    save_path = tmp_path / "kmeans.pkl"
    clf.save(save_path)
    loaded = OnlineClassifier.load(save_path)
    assert loaded.choice == ClassifierChoice.INCREMENTAL_KMEANS
    assert loaded.is_fitted
    assert loaded.n_samples_ == 6
    np.testing.assert_array_equal(loaded.predict([[5.0, 5.0]]), preds[:1])
    np.testing.assert_allclose(loaded.predict_proba([[5.0, 5.0]]), probas[:1])


def test_incremental_kmeans_inferred_clusters() -> None:
    clf = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS, random_state=42)
    X = np.array([[10.0, 0.0], [10.1, 0.1], [0.0, 10.0], [-10.0, 0.0]])
    y = np.array([0, 0, 1, 2])
    clf.partial_fit(X, y=y)

    assert clf.clf.n_clusters == 3
    assert clf.classes_ == [0, 1, 2]
    preds = clf.predict(X)
    assert len(preds) == 4
    probas = clf.predict_proba(X)
    assert probas.shape == (4, 3)
    assert np.allclose(probas.sum(axis=1), 1.0)


def test_incremental_kmeans_fit_method() -> None:
    clf = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS, n_clusters=2, random_state=42)
    X = np.array([[1.0, 1.0], [1.1, 0.9], [-1.0, -1.0], [-0.9, -1.1]])
    clf.fit(X)

    assert clf.is_fitted
    assert clf.n_samples_ == 4
    preds = clf.predict(X)
    assert len(preds) == 4


def test_supervised_requires_y() -> None:
    for choice in [ClassifierChoice.SGD, ClassifierChoice.PASSIVE_AGGRESSIVE]:
        clf = OnlineClassifier(choice=choice)
        with pytest.raises(ValueError, match="y is required"):
            clf.fit([[1.0, 1.0]])
        with pytest.raises(ValueError, match="y is required"):
            clf.partial_fit([[1.0, 1.0]])


def test_backward_compatibility_v1_saved_model(tmp_path: Any) -> None:
    class OldOnlineClassifierV1:
        def __init__(self) -> None:
            self.classes_ = [0, 1]
            self.clf = SGDClassifier(loss="log_loss", random_state=42)
            self.is_fitted = True

    old_obj = OldOnlineClassifierV1()
    X = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y = np.array([1, 0])
    old_obj.clf.fit(X, y)

    v1_file = tmp_path / "v1_legacy.pkl"
    with open(v1_file, "wb") as f:
        new_clf = OnlineClassifier()
        if "choice" in new_clf.__dict__:
            del new_clf.__dict__["choice"]
        if "n_samples_" in new_clf.__dict__:
            del new_clf.__dict__["n_samples_"]
        new_clf.classes_ = [0, 1]
        new_clf.clf = old_obj.clf
        new_clf.is_fitted = True
        pickle.dump(new_clf, f)

    loaded = OnlineClassifier.load(v1_file)
    assert loaded.choice == ClassifierChoice.SGD
    assert loaded.n_samples_ == 0
    assert loaded.is_fitted
    preds = loaded.predict([[1.0, 1.0], [-1.0, -1.0]])
    assert list(preds) == [1, 0]
    probas = loaded.predict_proba([[1.0, 1.0]])
    assert probas.shape == (1, 2)
    assert np.allclose(probas.sum(axis=1), 1.0)
