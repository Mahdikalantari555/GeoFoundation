# Tasks: geolearn-feedback-to-training-pipeline

- [x] Task 1: TrainingPipeline implementation
  - Acceptance: `TrainingPipeline` class reads accepted candidates from GeoMemory's candidate_memory table (via direct SQLite read with schema known from geomemory), groups by key, calls `partial_fit()` in batches of 10. Returns dict of `{key: {samples_trained, total_n_samples}}`.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/test_training_pipeline.py -v`
  - Files: `libs/geolearn/geolearn/training_pipeline.py`, `libs/geolearn/tests/test_training_pipeline.py`

- [x] Task 2: Pending count tracking
  - Acceptance: `training_pipeline.pending_count()` returns correct counts per key for accepted-but-not-yet-trained candidates.
  - Verify: same test file as Task 1.
  - Files: `libs/geolearn/geolearn/training_pipeline.py` (add method)

- [x] Task 3: GeoAgent tools
  - Acceptance: `geo_train_on_feedback(feedback_ids?)` and `geo_pending_training_count()` registered in registry; both return structured ToolResult values. `[rs]` extra required (pulls in geolearn).
  - Verify: `python -c "from geoagent.registry import Registry; r=Registry(); print('geo_train_on_feedback' in r.names())"` is True
  - Files: `libs/geoagent/src/geoagent/tools/geolearn_tools.py` (new), `libs/geoagent/src/geoagent/__init__.py`

- [x] Task 4: Update geolearn pyproject.toml
  - Acceptance: `geolearn` declares `[rs]` extra that pulls in `geomemory` (for candidate memory access) as a soft dependency — import is lazy inside TrainingPipeline.
  - Verify: `pip install -e libs/geolearn[rs] && python -c "from geolearn.training_pipeline import TrainingPipeline"` works
  - Files: `libs/geolearn/pyproject.toml`

- [x] Task 5: Gates
  - Acceptance: all geolearn tests pass; ruff clean; geoagent tests pass.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src libs/geoagent/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (pipeline before tools), 4 independent, all→5.
