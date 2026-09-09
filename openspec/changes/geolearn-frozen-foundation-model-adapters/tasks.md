# Tasks: geolearn-frozen-foundation-model-adapters

- [ ] Task 1: FrozenEmbeddingAdapter
  - Acceptance: `predict(embedding, key)` finds k nearest labeled neighbors via `EmbeddingCache.nn_lookup()`, returns weighted-vote PredictionResult with `source="nn_fallback"`.
  - Verify: `pytest libs/geolearn/tests/test_adapter.py -v`
  - Files: `libs/geolearn/geolearn/adapter.py`, `libs/geolearn/tests/test_adapter.py`

- [ ] Task 2: Auto-selection in ClassifierStore
  - Acceptance: When `n_training_samples < 30`, prediction routes through adapter; otherwise through classifier. Flag `source` in result distinguishes paths.
  - Verify: integration test with simulated low-sample and high-sample scenarios.
  - Files: `libs/geolearn/geolearn/classifier.py` (extension)

- [ ] Task 3: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2, all→3.
