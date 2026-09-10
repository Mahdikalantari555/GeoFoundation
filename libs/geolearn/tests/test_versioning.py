import sqlite3
import numpy as np
import pytest

from geolearn.classifier import OnlineClassifier
from geolearn.persistence import ClassifierStore
from geolearn.versioning import ModelVersion, ModelVersionManager


def test_version_save_and_list(tmp_path):
    mgr = ModelVersionManager(tmp_path)
    key = ("wheat", "khuzestan")

    clf1 = OnlineClassifier(random_state=42)
    clf1.fit([[1.0, 2.0], [-1.0, -2.0]], [1, 0])
    v1 = mgr.save_version(key, clf1, n_samples=2)

    assert isinstance(v1, ModelVersion)
    assert v1.version == 1
    assert v1.key == key
    assert len(v1.sha256) == 64
    assert v1.n_samples == 2

    # Verify file pattern on disk
    key_dir = mgr._key_dir(key)
    pkl_files = list(key_dir.glob("0001_*.pkl"))
    assert len(pkl_files) == 1
    assert (key_dir / "classifier.pkl").exists()

    # Save second version
    clf2 = OnlineClassifier(random_state=42)
    clf2.fit([[2.0, 4.0], [-2.0, -4.0]], [1, 0])
    v2 = mgr.save_version(key, clf2, n_samples=4)

    assert v2.version == 2

    # list_versions descending
    versions = mgr.list_versions(key)
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1

    # list_versions without key
    all_versions = mgr.list_versions()
    assert len(all_versions) == 2


def test_rollback_to_prior_version(tmp_path):
    mgr = ModelVersionManager(tmp_path)
    key = ("corn", "shiraz")

    # Version 1: trained to predict class 0 for [1.0, 0.0]
    clf1 = OnlineClassifier(random_state=42)
    clf1.fit([[1.0, 0.0], [0.0, 1.0]], [0, 1])
    mgr.save_version(key, clf1, n_samples=2)

    # Version 2: trained with opposite labels
    clf2 = OnlineClassifier(random_state=42)
    clf2.fit([[1.0, 0.0], [0.0, 1.0]], [1, 0])
    mgr.save_version(key, clf2, n_samples=2)

    # Currently active classifier is Version 2
    active_clf = OnlineClassifier.load(mgr._key_dir(key) / "classifier.pkl")
    assert list(active_clf.predict([[1.0, 0.0]])) == [1]

    # Rollback to Version 1
    ok = mgr.rollback_to(key, 1, reason="Undo corrupted batch")
    assert ok is True

    # Active classifier should now predict like Version 1
    restored_clf = OnlineClassifier.load(mgr._key_dir(key) / "classifier.pkl")
    assert list(restored_clf.predict([[1.0, 0.0]])) == [0]

    # Check rollback_history recorded in DB
    with sqlite3.connect(mgr.db_path) as conn:
        cur = conn.execute(
            "SELECT from_version, to_version, reason FROM rollback_history WHERE key_crop = ? AND key_region = ?",
            ("corn", "shiraz"),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 2
        assert row[1] == 1
        assert "Undo corrupted batch" in row[2]

    # Rollback to non-existent version returns False
    assert mgr.rollback_to(key, 99) is False


def test_garbage_collection_keeps_last_10(tmp_path):
    mgr = ModelVersionManager(tmp_path)
    key = ("barley", "esfahan")

    clf = OnlineClassifier(random_state=42)
    clf.fit([[1.0], [-1.0]], [1, 0])

    # Save 13 versions
    for i in range(1, 14):
        mgr.save_version(key, clf, n_samples=i)

    versions = mgr.list_versions(key)
    # Only 10 versions should remain
    assert len(versions) == 10
    remaining_version_nums = [v.version for v in versions]
    assert remaining_version_nums == list(range(13, 3, -1))  # 13 down to 4

    # Versions 1, 2, 3 must be deleted from disk
    key_dir = mgr._key_dir(key)
    for v in [1, 2, 3]:
        matching = list(key_dir.glob(f"{v:04d}_*.pkl"))
        assert len(matching) == 0

    # Rollback to deleted version returns False
    assert mgr.rollback_to(key, 3) is False


def test_classifier_store_integration(tmp_path):
    store = ClassifierStore(tmp_path)
    key = ("rice", "gilan")

    clf1 = OnlineClassifier(random_state=42)
    clf1.fit([[1.0, 2.0], [-1.0, -2.0]], [1, 0])
    version_hash = store.save_classifier(key, clf1, n_samples=2)
    assert len(version_hash) == 64

    # Store list_versions
    versions = store.list_versions(key)
    assert len(versions) == 1
    assert versions[0].version == 1

    # Train second version
    clf2 = OnlineClassifier(random_state=42)
    clf2.fit([[1.0, 2.0], [-1.0, -2.0]], [0, 1])
    store.save_classifier(key, clf2, n_samples=4)

    assert list(store.get_classifier(key).predict([[1.0, 2.0]])) == [0]

    # Rollback through store
    ok = store.rollback_to(key, 1)
    assert ok is True
    assert list(store.get_classifier(key).predict([[1.0, 2.0]])) == [1]
