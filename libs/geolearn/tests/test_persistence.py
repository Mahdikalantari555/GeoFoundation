import numpy as np
import pytest
from geolearn.classifier import OnlineClassifier
from geolearn.persistence import ClassifierStore

def test_classifier_store_save_and_get(tmp_path):
    store = ClassifierStore(tmp_path)
    clf = OnlineClassifier()
    clf.fit([[1.0, 2.0], [-1.0, -2.0]], [1, 0])

    version = store.save_classifier(("wheat", "khuzestan"), clf, n_samples=2)
    assert len(version) == 64  # sha256

    loaded_clf = store.get_classifier(("wheat", "khuzestan"))
    assert loaded_clf.is_fitted
    assert list(loaded_clf.predict([[1.0, 2.0]])) == [1]

def test_classifier_store_key_isolation_and_fallback(tmp_path):
    store = ClassifierStore(tmp_path)
    global_clf = OnlineClassifier()
    global_clf.fit([[1.0], [-1.0]], [1, 0])
    store.save_classifier(("unknown", "global"), global_clf, n_samples=2)

    # Key that has no specific classifier falls back to global
    fallback_clf = store.get_classifier(("barley", "fars"))
    assert fallback_clf.is_fitted
    assert list(fallback_clf.predict([[1.0]])) == [1]
