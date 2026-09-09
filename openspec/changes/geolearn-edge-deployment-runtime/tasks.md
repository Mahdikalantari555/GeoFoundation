# Tasks: geolearn-edge-deployment-runtime

- [ ] Task 1: EdgeExport serialization
  - Acceptance: `export_for_edge(output_dir)` writes `classifier.json` (classes as strings, n_features as int) and `weights.npy` / `intercept.npy` (base64-encoded inside JSON, or separate npz — choose one approach and document it). Manifest.txt includes version, n_samples, export date.
  - Verify: `pytest libs/geolearn/tests/test_edge_export.py -v`
  - Files: `libs/geolearn/geolearn/edge_export.py`, `libs/geolearn/tests/test_edge_export.py`

- [ ] Task 2: EdgeLoader
  - Acceptance: `EdgeLoader(output_dir)` loads the bundle and provides `predict(X)` and `predict_proba(X)` using only numpy. Output matches original classifier on held-out test data (within float tolerance).
  - Verify: round-trip test: train in sklearn → export → load in EdgeLoader → predict same X → compare labels exactly.
  - Files: `libs/geolearn/geolearn/edge_loader.py`, tests in same file

- [ ] Task 3: geo_export_for_edge tool
  - Acceptance: `rs_compute_et`-style tool accepting optional `key` (default global). Writes bundle to output_dir, returns artifact refs for all output files.
  - Verify: tool registered; call produces valid edge bundle.
  - Files: `libs/geoagent/src/geoagent/tools/geolearn_tools.py` (extend)

- [ ] Task 4: Gates
  - Acceptance: all tests green; ruff/mypy clean; edge loader works in clean env without scikit-learn (simulated by monkeypatching out sklearn during import test).
  - Verify: `conda run -n geospatial pytest libs/geolearn/tests -q && conda run -n geospatial ruff check libs/geolearn/src libs/geoagent/src && conda run -n geospatial mypy --strict libs/geolearn/src`
  - Files: all above

Dependencies: 1→2 (export before loader), 3 depends on 1, all→4.
