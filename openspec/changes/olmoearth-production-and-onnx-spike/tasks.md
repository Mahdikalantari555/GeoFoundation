# Tasks: olmoearth-production-and-onnx-spike

## Track A: Production wiring

- [ ] Task A1: Ingest hook — call embedder after raster persist
  - Acceptance: `GeoTiffLoader.load()` returns parsed objects; after `persist_scene()`, if `settings.vision_path` is set and torch is available, the loader (or a post-processing step in the pipeline) calls `OlmoEarthVisionEmbedder.embed_images()` on tile previews and stores the result in `ImageIndex`.
  - Verify: integration test ingests a synthetic GeoTIFF with vision configured; asserts an embedding record exists in the image index.
  - Files: `src/geomemory/ingest/pipeline.py`, `src/geomemory/index/image_index.py`

- [ ] Task A2: Persist image index on ingest completion
  - Acceptance: After embed, `ImageIndex.save(index_dir / "image", manifest)` is called so embeddings survive workspace reopen. On next open, `ws.image_index()` loads the persisted index.
  - Verify: unit test — save then load round-trip preserves all embeddings.
  - Files: `src/geomemory/index/image_index.py`

- [ ] Task A3: Dashboard image-search page
  - Acceptance: New or extended dashboard page lets the user upload a reference satellite image and see the top-k visually similar ingested scenes/tiles. Uses `ws.search_images(query_vector, top_k)`.
  - Verify: Streamlit page renders; manual smoke test with a test GeoTIFF.
  - Files: `apps/dashboard/pages/image_search.py` (new), `apps/dashboard/app.py` (nav wire)

- [ ] Task A4: Test coverage for track A
  - Acceptance: Integration tests for ingest-with-vision, empty-vision-config (no-op), missing-torch-extra (graceful skip).
  - Verify: `conda run -n geospatial pytest libs/geomemory/tests -q`
  - Files: `tests/integration/test_vision_ingest.py`

## Track B: ONNX export spike

- [ ] Task B1: ONNX export script
  - Acceptance: `scripts/export_olmoearth_onnx.py --input weights.pth --output out/` produces `model.onnx` and a config manifest. Script exits 0 on success, 1 on missing input.
  - Verify: manual run against a known Nano checkpoint; onnxruntime can load the exported model.
  - Files: `scripts/export_olmoearth_onnx.py`

- [ ] Task B2: Quality comparison benchmark
  - Acceptance: `scripts/benchmark_olmoearth_onnx.py` runs both native torch and ONNX models on ≥20 fixed satellite tiles, outputs mean cosine distance and per-sample table.
  - Verify: output CSV; mean distance ≤ 0.02 passes the acceptance threshold.
  - Files: `scripts/benchmark_olmoearth_onnx.py`

- [ ] Task B3: Latency and size benchmark
  - Acceptance: Benchmark measures mean embedding latency (50 runs) and model file size for both implementations; outputs a comparison table.
  - Verify: table included in spike report; both models run on CPU.
  - Files: `scripts/benchmark_olmoearth_onnx.py` (extends B2)

- [ ] Task B4: Spike report
  - Acceptance: `docs/onnx-spike-report.md` summarizes export outcome, quality delta, latency delta, size delta, and recommendation (proceed with ONNX / stay with torch / inconclusive).
  - Verify: report read by reviewer; decision recorded.
  - Files: `docs/onnx-spike-report.md`

Dependencies: A1→A2, A1→A3 (dashboard uses same image_index), A1→A4, B1→B2→B3 (sequential benchmark), B1 independent of A track. All→final validation.
