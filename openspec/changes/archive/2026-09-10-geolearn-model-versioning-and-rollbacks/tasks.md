# Tasks: geolearn-model-versioning-and-rollbacks

- [x] Task 1: Versioned file naming + ModelVersion dataclass
  - Acceptance: Every save produces `<version:04d>_<ISO_TS>.pkl`. `list_versions(key)` returns sorted ModelVersion objects with sha256 of each file.
  - Verify: `pytest libs/geolearn/tests/test_versioning.py -v`
  - Files: `libs/geolearn/geolearn/versioning.py`, `libs/geolearn/tests/test_versioning.py`

- [x] Task 2: rollback_to implementation
  - Acceptance: Restores classifier from specified version file. Logs rollback event to `rollback_history` table (key, from_version, to_version, timestamp, reason). Returns True on success, False if version missing.
  - Verify: save version 1, save version 2, rollback to 1, assert predictions match version-1 behavior.
  - Files: `libs/geolearn/geolearn/versioning.py`

- [x] Task 3: Garbage collection
  - Acceptance: After each save, versions beyond the last 10 per key are deleted from disk. Orphaned rows removed from version listing. Rollback to deleted version returns False.
  - Verify: create 12 versions, save 13th, assert version 3 is gone from disk and listings.
  - Files: `libs/geolearn/geolearn/versioning.py`

- [x] Task 4: GeoAgent tools
  - Acceptance: `geo_list_model_versions(key?)` returns structured list. `geo_rollback_model(key, version)` performs rollback and returns before/after n_samples.
  - Verify: tools registered; call returns correct shape.
  - Files: `libs/geoagent/src/geoagent/tools/geolearn_tools.py` (extend)

- [x] Task 5: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src libs/geoagent/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (gc after rollback), 4 depends on 2, all→5.
