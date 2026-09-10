# Tasks: geolearn-confidence-and-uncertainty-modeling

- [x] Task 1: CalibrationCurve
  - Acceptance: Maintains rolling buffer of (proba, is_correct). Fits isotonic regression on ≥10 samples; returns raw proba when insufficient. `calibrate(proba) -> float` applies transformation.
  - Verify: `pytest libs/geolearn/tests/test_calibration.py -v`
  - Files: `libs/geolearn/geolearn/calibration.py`, `libs/geolearn/tests/test_calibration.py`

- [x] Task 2: Entropy computation
  - Acceptance: `prediction_entropy([1.0, 0.0]) == 0.0`; `prediction_entropy([0.33, 0.33, 0.34]) ≈ 1.09`. Handles edge case of single-class input gracefully.
  - Verify: same test file.
  - Files: `libs/geolearn/geolearn/calibration.py`

- [x] Task 3: Combined confidence score
  - Acceptance: `compute_final_confidence(calibrated_proba, entropy)` applies 0.7/0.3 blend formula. Entropy capping at log(2) ensures score ∈ [0, 1].
  - Verify: unit tests for boundary values.
  - Files: `libs/geolearn/geolearn/calibration.py`

- [x] Task 4: Entropy-based abstention in ClassifierStore
  - Acceptance: When entropy > 0.8 bits, prediction is marked abstain even if calibrated proba > 0.6. Tested with synthetic multi-class distributions.
  - Verify: integration test with high-entropy input.
  - Files: `libs/geolearn/geolearn/classifier.py` (extend)

- [x] Task 5: Gates
  - Acceptance: all tests green; ruff/mypy clean.
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2→3 (calibration → entropy → blend), 4 depends on 1+3, all→5.
