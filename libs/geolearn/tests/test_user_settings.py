import sqlite3
import numpy as np
import pytest

from geolearn.classifier import OnlineClassifier
from geolearn.confidence import ConfidenceModel
from geolearn.persistence import ClassifierStore
from geolearn.user_settings import UserSettings, UserSettingsStore


def test_user_settings_dataclass():
    settings = UserSettings(user_id="user_test")
    assert settings.user_id == "user_test"
    assert settings.confidence_threshold == 0.6
    assert settings.preferred_classifier == "sgd"
    assert settings.auto_train_on_feedback is True
    assert isinstance(settings.updated_at, str)


def test_user_settings_store_crud(tmp_path):
    store = UserSettingsStore(tmp_path)

    # 1. get_or_default returns default values for new user
    s_default = store.get_or_default("new_user")
    assert s_default.user_id == "new_user"
    assert s_default.confidence_threshold == 0.6
    assert s_default.preferred_classifier == "sgd"
    assert s_default.auto_train_on_feedback is True

    # 2. update persists modifications
    updated = store.update(
        "new_user",
        confidence_threshold=0.85,
        preferred_classifier="passive_aggressive",
        auto_train_on_feedback=False,
    )
    assert updated.confidence_threshold == 0.85
    assert updated.preferred_classifier == "passive_aggressive"
    assert updated.auto_train_on_feedback is False

    # 3. Reload from fresh instance
    reloaded_store = UserSettingsStore(tmp_path)
    fetched = reloaded_store.get_or_default("new_user")
    assert fetched.confidence_threshold == 0.85
    assert fetched.preferred_classifier == "passive_aggressive"
    assert fetched.auto_train_on_feedback is False

    # 4. Partial update retains existing fields
    partially_updated = store.update("new_user", confidence_threshold=0.7)
    assert partially_updated.confidence_threshold == 0.7
    assert partially_updated.preferred_classifier == "passive_aggressive"
    assert partially_updated.auto_train_on_feedback is False

    # 5. list_all
    store.update("another_user", confidence_threshold=0.5)
    all_settings = store.list_all()
    assert len(all_settings) == 2


def test_predict_for_key_user_threshold_override(tmp_path):
    store = ClassifierStore(tmp_path)
    clf = OnlineClassifier()
    X = np.array([[1.0, 1.0], [-1.0, -1.0]])
    y = np.array([1, 0])
    clf.fit(X, y)
    store.save_classifier(("wheat", "khuzestan"), clf, n_samples=2)

    # Configure user with lenient threshold (0.3)
    store.user_settings_store.update("lenient_user", confidence_threshold=0.3)
    # Configure user with strict threshold (0.95)
    store.user_settings_store.update("strict_user", confidence_threshold=0.95)

    test_point = [[0.2, 0.2]]

    # For default user (threshold 0.6)
    res_default = store.predict_for_key(test_point, key=("wheat", "khuzestan"))
    # Lenient user should not abstain if confidence >= 0.3
    res_lenient = store.predict_for_key(test_point, key=("wheat", "khuzestan"), user_id="lenient_user")
    # Strict user should abstain if confidence < 0.95
    res_strict = store.predict_for_key(test_point, key=("wheat", "khuzestan"), user_id="strict_user")

    conf = res_default.confidence[0]
    if conf < 0.95 and conf >= 0.3:
        assert res_lenient.abstain is False
        assert res_strict.abstain is True

    # Missing user_id falls back to default 0.6
    res_unregistered = store.predict_for_key(test_point, key=("wheat", "khuzestan"), user_id="nonexistent")
    assert res_unregistered.abstain == res_default.abstain


def test_exact_threshold_boundary():
    # ConfidenceModel abstains when confidence < threshold
    # So confidence == threshold is NOT abstained
    conf_model = ConfidenceModel(threshold=0.6)
    # Mock probability that produces confidence
    assert conf_model.is_abstain(0.5999) is True
    assert conf_model.is_abstain(0.6000) is False
    assert conf_model.is_abstain(0.6001) is False
