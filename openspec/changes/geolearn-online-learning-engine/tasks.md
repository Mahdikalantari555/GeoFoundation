# Tasks: geolearn-online-learning-engine

- [ ] Task 1: StreamingWindow class
  - Acceptance: `test_online_engine.py` covers insert, overflow (oldest discarded), items() ordering.
  - Verify: `pytest libs/geolearn/tests/test_online_engine.py -v`
  - Files: `libs/geolearn/geolearn/streaming.py`, `libs/geolearn/tests/test_online_engine.py`

- [ ] Task 2: SimpleDriftDetector
  - Acceptance: Triggers when error rate over window exceeds threshold. Test covers exact-threshold boundary.
  - Verify: same test file.
  - Files: `libs/geolearn/geolearn/drift.py`

- [ ] Task 3: RiverDriftDetector (optional)
  - Acceptance: When `[river]` extra is installed, uses PageHinkley; otherwise falls back to SimpleDriftDetector without ImportError.
  - Verify: `pytest ... -v` passes in both environments (with and without river).
  - Files: `libs/geolearn/geolearn/drift.py` (conditional import)

- [ ] Task 4: OnlineScheduler
  - Acceptance: Batches up to batch_size or min_interval_s, whichever comes first. Test covers both triggers independently.
  - Verify: same test file.
  - Files: `libs/geolearn/geolearn/scheduler.py`, tests added to `test_online_engine.py`

- [ ] Task 5: Integration with ClassifierStore
  - Acceptance: `ClassifierStore` accepts an optional `scheduler` parameter; when provided, wraps partial_fit calls through the scheduler.
  - Verify: end-to-end test with synthetic feedback stream.
  - Files: `libs/geolearn/geolearn/classifier.py` (extension)

- [ ] Task 6: Gates
  - Acceptance: full test suite green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (drift layer), 4 depends on 2, 5 depends on 4, all→6.
