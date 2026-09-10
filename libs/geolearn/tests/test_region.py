import sqlite3
import numpy as np
import pytest

from geolearn.classifier import OnlineClassifier
from geolearn.persistence import ClassifierStore
from geolearn.region import (
    build_hierarchical_key,
    get_parent_key,
    parse_hierarchical_key,
    transfer_weights,
)


def test_build_hierarchical_key():
    assert build_hierarchical_key("wheat", "khuzestan") == "wheat.khuzestan"
    assert build_hierarchical_key("wheat", "khuzestan", "dezful") == "wheat.khuzestan.dezful"
    assert build_hierarchical_key("  wheat ", " khuzestan  ", "  dezful ") == "wheat.khuzestan.dezful"
    assert build_hierarchical_key("wheat", "khuzestan", None) == "wheat.khuzestan"
    assert build_hierarchical_key("wheat", "khuzestan", "") == "wheat.khuzestan"


def test_parse_hierarchical_key():
    assert parse_hierarchical_key("wheat.khuzestan") == ("wheat", "khuzestan", None)
    assert parse_hierarchical_key("wheat.khuzestan.dezful") == ("wheat", "khuzestan", "dezful")
    assert parse_hierarchical_key(("wheat", "khuzestan")) == ("wheat", "khuzestan", None)
    assert parse_hierarchical_key(("wheat", "khuzestan", "dezful")) == ("wheat", "khuzestan", "dezful")

    with pytest.raises(ValueError):
        parse_hierarchical_key("singlekey")

    with pytest.raises(ValueError):
        parse_hierarchical_key(("singlekey",))

    with pytest.raises(TypeError):
        parse_hierarchical_key(123)  # type: ignore


def test_get_parent_key():
    assert get_parent_key("wheat.khuzestan.dezful") == "wheat.khuzestan"
    assert get_parent_key("wheat.khuzestan") is None
    assert get_parent_key(("wheat", "khuzestan", "dezful")) == "wheat.khuzestan"
    assert get_parent_key(("wheat", "khuzestan")) is None


def test_weight_transfer_and_divergence():
    parent = OnlineClassifier(random_state=42)
    X = np.array([[1.0, 2.0], [-1.0, -2.0]])
    y = np.array([1, 0])
    parent.fit(X, y)

    child = transfer_weights(parent)
    assert child.is_fitted
    assert child.n_samples_ == 0
    assert np.allclose(child.clf.coef_, parent.clf.coef_)
    assert np.allclose(child.clf.intercept_, parent.clf.intercept_)

    # Child fits new sample; parent remains unchanged
    child_X = np.array([[2.0, 3.0]])
    child_y = np.array([1])
    child.partial_fit(child_X, child_y)

    assert not np.allclose(child.clf.coef_, parent.clf.coef_)
    # Parent weights did not mutate
    preds_parent = parent.predict([[1.0, 2.0]])
    assert preds_parent[0] == 1


def test_classifier_store_get_or_create_key_and_inheritance(tmp_path):
    store = ClassifierStore(tmp_path)

    # Train parent
    parent_clf = OnlineClassifier(random_state=42)
    parent_clf.fit([[1.0, 1.0], [-1.0, -1.0]], [1, 0])
    store.save_classifier(("wheat", "khuzestan"), parent_clf, n_samples=2)

    # get_or_create_key for sub-region triggers weight transfer
    key = store.get_or_create_key("wheat", "khuzestan", "dezful")
    assert key == "wheat.khuzestan.dezful"

    sub_clf = store.get_classifier(key)
    assert sub_clf.is_fitted
    assert np.allclose(sub_clf.clf.coef_, parent_clf.clf.coef_)

    # Train sub-region; ensure divergence
    sub_clf.partial_fit([[-2.0, -2.0]], [0])
    store.save_classifier(key, sub_clf, n_samples=3)

    reloaded_sub = store.get_classifier(key)
    reloaded_parent = store.get_classifier(("wheat", "khuzestan"))
    assert not np.allclose(reloaded_sub.clf.coef_, reloaded_parent.clf.coef_)


def test_schema_migration_for_sub_region(tmp_path):
    db_file = tmp_path / "geolearn.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE classifier_state (
                key_crop TEXT NOT NULL,
                key_region TEXT NOT NULL,
                version TEXT NOT NULL,
                fitted_at TEXT NOT NULL,
                n_samples INTEGER NOT NULL,
                PRIMARY KEY (key_crop, key_region)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO classifier_state VALUES (?, ?, ?, ?, ?)
            """,
            ("wheat", "khuzestan", "ver1", "2026-09-10T10:00:00Z", 100),
        )
        conn.commit()

    store = ClassifierStore(tmp_path)

    with sqlite3.connect(db_file) as conn:
        cur = conn.execute("SELECT key_crop, key_region, sub_region, version FROM classifier_state")
        row = cur.fetchone()
        assert row[0] == "wheat"
        assert row[1] == "khuzestan"
        assert row[2] is None
        assert row[3] == "ver1"

    # Now save a sub-region model in the migrated DB
    sub_clf = OnlineClassifier()
    sub_clf.fit([[1.0], [-1.0]], [1, 0])
    store.save_classifier(("wheat", "khuzestan", "dezful"), sub_clf, n_samples=10)

    with sqlite3.connect(db_file) as conn:
        cur = conn.execute("SELECT key_crop, key_region, sub_region, n_samples FROM classifier_state ORDER BY sub_region NULLS FIRST")
        rows = cur.fetchall()
        assert len(rows) == 2
        assert rows[0] == ("wheat", "khuzestan", None, 100)
        assert rows[1] == ("wheat", "khuzestan", "dezful", 10)
