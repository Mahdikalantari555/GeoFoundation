# Tasks: geolearn-personalization-profiles

- [x] Task 1: UserProfile + ProfileStore
  - Acceptance: `UserProfile` dataclass with all fields; `ProfileStore` implements get_or_create, update, list_all. SQLite table `user_profiles` created automatically on first use.
  - Verify: `pytest libs/geolearn/tests/test_profiles.py -v`
  - Files: `libs/geolearn/geolearn/profiles.py`, `libs/geolearn/tests/test_profiles.py`

- [x] Task 2: Schema migration
  - Acceptance: Existing geolearn.db (without user_profiles table) is auto-migrated on first ProfileStore access. Migration runs idempotently.
  - Verify: create empty geolearn.db, instantiate ProfileStore, assert table exists.
  - Files: `libs/geolearn/geolearn/profiles.py` (add _migrate method)

- [x] Task 3: ClassifierStore integration
  - Acceptance: `ClassifierStore.select_key(user_id, region, crop_type)` checks profile first; falls back to default if no profile.
  - Verify: unit test covering profile-present and profile-absent paths.
  - Files: `libs/geolearn/geolearn/classifier.py` (extension)

- [x] Task 4: Gates
  - Acceptance: all geolearn tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (migration before integration), all→4.
