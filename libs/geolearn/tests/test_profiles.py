import sqlite3
import pytest

from geolearn.persistence import ClassifierStore
from geolearn.profiles import ProfileStore, UserProfile


def test_user_profile_dataclass():
    profile = UserProfile(user_id="user1", region="khuzestan")
    assert profile.user_id == "user1"
    assert profile.region == "khuzestan"
    assert profile.crop_type == "unknown"
    assert profile.preferred_classifier == "sgd"
    assert profile.trained_at is None
    assert profile.n_training_samples == 0

    custom = UserProfile(
        user_id="u2",
        region="fars",
        crop_type="wheat",
        preferred_classifier="passive_aggressive",
        trained_at="2026-09-10T12:00:00Z",
        n_training_samples=42,
    )
    assert custom.crop_type == "wheat"
    assert custom.preferred_classifier == "passive_aggressive"
    assert custom.n_training_samples == 42


def test_profile_store_get_or_create_and_idempotency(tmp_path):
    store = ProfileStore(tmp_path)

    # First call creates default profile
    p1 = store.get_or_create("anonymous", "khuzestan")
    assert p1.user_id == "anonymous"
    assert p1.region == "khuzestan"
    assert p1.preferred_classifier == "sgd"
    assert p1.n_training_samples == 0

    # Second call returns the same profile (idempotent)
    p2 = store.get_or_create("anonymous", "khuzestan")
    assert p1.user_id == p2.user_id
    assert p1.region == p2.region

    # Separate region gives distinct profile
    p3 = store.get_or_create("anonymous", "fars")
    assert p3.region == "fars"

    all_profiles = store.list_all()
    assert len(all_profiles) == 2


def test_profile_store_update(tmp_path):
    store = ProfileStore(tmp_path)
    store.get_or_create("user_alpha", "tehran")

    updated = store.update(
        "user_alpha",
        "tehran",
        crop_type="barley",
        preferred_classifier="passive_aggressive",
        n_training_samples=150,
        trained_at="2026-09-10T14:30:00Z",
    )
    assert updated.crop_type == "barley"
    assert updated.preferred_classifier == "passive_aggressive"
    assert updated.n_training_samples == 150
    assert updated.trained_at == "2026-09-10T14:30:00Z"

    # Reload from fresh store instance to verify persistence
    reloaded_store = ProfileStore(tmp_path)
    fetched = reloaded_store.get("user_alpha", "tehran")
    assert fetched is not None
    assert fetched.crop_type == "barley"
    assert fetched.preferred_classifier == "passive_aggressive"
    assert fetched.n_training_samples == 150


def test_profile_store_schema_auto_migration(tmp_path):
    # Pre-create empty geolearn.db without user_profiles table
    db_file = tmp_path / "geolearn.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        conn.commit()

    # ProfileStore should auto-migrate and create user_profiles
    store = ProfileStore(tmp_path)
    with sqlite3.connect(db_file) as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'")
        assert cur.fetchone() is not None

    p = store.get_or_create("migrated_user", "isfahan")
    assert p.user_id == "migrated_user"


def test_classifier_store_select_key_with_profiles(tmp_path):
    store = ClassifierStore(tmp_path)

    # 1. Non-existent profile falls back to default ("sgd")
    key_default = store.select_key("unknown_user", "khuzestan", "wheat")
    assert key_default == "wheat.khuzestan"

    # 2. Profile with sgd returns standard dotted key
    store.profile_store.get_or_create("user1", "khuzestan")
    key_sgd = store.select_key("user1", "khuzestan", "wheat")
    assert key_sgd == "wheat.khuzestan"

    # 3. Profile with preferred_classifier != sgd uses preferred classifier
    store.profile_store.update(
        "user2", "khuzestan", crop_type="wheat", preferred_classifier="passive_aggressive"
    )
    key_custom = store.select_key("user2", "khuzestan", "wheat")
    assert key_custom == "wheat.khuzestan.passive_aggressive"

    # 4. Anonymous user auto-creates profile
    key_anon = store.select_key("anonymous", "gilan", "rice")
    assert key_anon == "rice.gilan"
    anon_prof = store.profile_store.get("anonymous", "gilan")
    assert anon_prof is not None
