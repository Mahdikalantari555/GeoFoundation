# Tasks: geolearn-core-framework

- [ ] Task 1: Scaffold library structure
  - Acceptance: `libs/geolearn/pyproject.toml` exists with name=`geolearn`, requires-python=`>=3.10`, deps=`numpy>=1.24 scikit-learn>=1.3 joblib>=1.3`. Package directory `geolearn/` with `__init__.py` exporting `OnlineClassifier`, `EmbeddingCache`, `PredictionResult`, `ConfidenceModel`.
  - Verify: `conda run -n geospatial pip install -e libs/geolearn && python -c "from geolearn import OnlineClassifier, EmbeddingCache; print('ok')"`
  - Files: `libs/geolearn/pyproject.toml`, `libs/geolearn/geolearn/__init__.py`, `libs/geolearn/README.md`

- [ ] Task 2: EmbeddingCache implementation
  - Acceptance: `test_cache.py` covers insert, lookup hit/miss, nn_lookup with k=3, vector round-trip (numpy serialize/deserialize via joblib).
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/test_cache.py -v`
  - Files: `libs/geolearn/geolearn/cache.py`, `libs/geolearn/tests/test_cache.py`

- [ ] Task 3: OnlineClassifier wrapper
  - Acceptance: Tests cover `fit`/`partial_fit`/`predict`/`predict_proba`/`save`/`load`. First `partial_fit` stores classes; subsequent calls work without re-specifying classes. `predict` on unseen distribution returns plausible labels.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/test_classifier.py -v`
  - Files: `libs/geolearn/geolearn/classifier.py`, `libs/geolearn/tests/test_classifier.py`

- [ ] Task 4: ConfidenceModel
  - Acceptance: `test_confidence.py` covers threshold crossing (confidence above → not abstain, below → abstain), configurable threshold, edge case at exact threshold.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/test_confidence.py -v`
  - Files: `libs/geolearn/geolearn/confidence.py`, `libs/geolearn/tests/test_confidence.py`

- [ ] Task 5: ClassifierStore (per-key management)
  - Acceptance: `test_persistence.py` covers save/load round-trip, key isolation (two keys have independent classifiers), default key fallback when no specific classifier exists.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/test_persistence.py -v`
  - Files: `libs/geolearn/geolearn/persistence.py`, `libs/geolearn/tests/test_persistence.py`

- [ ] Task 6: Integration test + public API surface
  - Acceptance: Full pipeline test: cache embeddings → fit classifier on known labels → predict new asset → confidence check → abstain when low. Public exports verified: `from geolearn import OnlineClassifier, EmbeddingCache, PredictionResult, ConfidenceModel`.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests/ -v`
  - Files: `libs/geolearn/tests/test_integration.py`, `libs/geolearn/geolearn/__init__.py`

- [ ] Task 7: Phase 3 roadmap doc
  - Acceptance: `docs/phase3-roadmap.md` exists listing all Phase 3 changes (online-learning-engine, edge-deployment-runtime, model-versioning-and-rollbacks, frozen-foundation-model-adapters) with one-line description each. NOT implemented — documented only.
  - Verify: `cat libs/geolearn/docs/phase3-roadmap.md` shows all four items.
  - Files: `libs/geolearn/docs/phase3-roadmap.md`

- [ ] Task 8: Gates
  - Acceptance: all tests green; ruff clean; mypy --strict passes on geolearn/src.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3→4→5 (same lib, incremental), 6 depends on 1–5, 7 independent, all→8.
