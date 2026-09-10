# Tasks: geolearn-region-specific-adaptation

- [x] Task 1: Hierarchical key resolution
  - Acceptance: `get_or_create_key(crop, region, sub_region=None)` returns dotted string key. Parent key lookup works for missing sub-regions.
  - Verify: `pytest libs/geolearn/tests/test_region_adaptation.py -v`
  - Files: `libs/geolearn/geolearn/classifier.py` (extend), `libs/geolearn/tests/test_region_adaptation.py`

- [x] Task 2: Weight transfer on first sub-region access
  - Acceptance: First `partial_fit()` on sub-region copies parent's coef_ and intercept_ before adding own gradient. Post-transfer, sub-region diverges.
  - Verify: test asserting coef_ match immediately after first partial_fit, then divergence after second.
  - Files: `libs/geolearn/geolearn/classifier.py`

- [x] Task 3: Schema migration for sub_region column
  - Acceptance: Existing geolearn.db migrates automatically; nullable column allows legacy rows.
  - Verify: create db without sub_region, instantiate store, assert query succeeds.
  - Files: `libs/geolearn/geolearn/persistence.py` (migration)

- [x] Task 4: geo_select_region tool
  - Acceptance: `geo_select_region(crop_type, region)` returns active key + n_samples. Registered in geoagent registry under `[rs]` extra.
  - Verify: tool appears in registry; call returns valid response.
  - Files: `libs/geoagent/src/geoagent/tools/geolearn_tools.py` (extend)

- [x] Task 5: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src libs/geoagent/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (schema after logic), 4 independent of 1-3, all→5.
