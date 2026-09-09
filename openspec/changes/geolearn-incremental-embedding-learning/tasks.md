# Tasks: geolearn-incremental-embedding-learning

- [ ] Task 1: AssociationMap
  - Acceptance: `AssociationMap(half_life_days=90)` maintains (hash, label) → score dict. `update(hash, label)` increments and decays. `scores_for(hash) -> dict[label, score]` returns current scores.
  - Verify: `pytest libs/geolearn/tests/test_association.py -v`
  - Files: `libs/geolearn/geolearn/association.py`, `libs/geolearn/tests/test_association.py`

- [ ] Task 2: Blend integration
  - Acceptance: `OnlineClassifier.predict()` applies association-map blend (50/50 with classifier proba) when map has entries for the key. No blend applied when map is empty.
  - Verify: unit test with empty and populated maps.
  - Files: `libs/geolearn/geolearn/classifier.py` (extension)

- [ ] Task 3: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2, all→3.
