# Tasks: geolearn-lightweight-classifier-layer

- [ ] Task 1: Add ClassifierChoice enum and factory
  - Acceptance: `ClassifierChoice` enum defined; `OnlineClassifier(choice=ClassifierChoice.SGD)` selects the correct underlying sklearn class. Default remains SGD.
  - Verify: `pytest libs/geolearn/tests/test_classifier_choices.py -v`
  - Files: `libs/geolearn/geolearn/classifier.py`, `libs/geolearn/tests/test_classifier_choices.py`

- [ ] Task 2: PassiveAggressiveClassifier wrapper
  - Acceptance: `choice="passive_aggressive"` produces a classifier that accepts identical `partial_fit(X, y)` calls as SGD. Test covers noisier-label robustness (30% label noise → lower error than SGD on same data).
  - Verify: same test file.
  - Files: `libs/geolearn/geolearn/classifier.py`

- [ ] Task 3: IncrementalKMeans wrapper
  - Acceptance: `choice="incremental_kmeans"` accepts `partial_fit(X)` without labels (semi-supervised). `predict(X)` returns cluster assignments. `n_classes` inferred from unique labels in y if provided.
  - Verify: test covering label-free fit and labeled fit paths.
  - Files: `libs/geolearn/geolearn/classifier.py`

- [ ] Task 4: Backward-compatibility check
  - Acceptance: Existing code using `OnlineClassifier()` without `choice` parameter continues to work identically. Saved `.pkl` files from v1 (SGD only) load correctly under v2.
  - Verify: load a v1-style pickle in v2 context; assert predictions match.
  - Files: `libs/geolearn/tests/test_backward_compat.py`

- [ ] Task 5: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (enum first, then each classifier), 4 depends on 1, all→5.
