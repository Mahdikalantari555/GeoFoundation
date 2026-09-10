# geolearn-edge-deployment-runtime — Specification (v0.2)

Portable classifier export for CPU/mobile/UAV deployment without scikit-learn runtime.

## Requirements

### Requirement: EdgeExport format
`OnlineClassifier.export_for_edge(output_dir)` SHALL produce:
- `classifier.json`: model metadata (classes, n_features, exported_at timestamp)
- `weights.npy`: flattened weight array (base64-encoded in JSON for portability)
- `intercept.npy`: bias array (same treatment)
- `manifest.txt`: human-readable summary of version, n_samples, export date

### Requirement: EdgeLoader
`EdgeLoader(output_dir)` SHALL load the JSON+npy bundle and provide:
- `predict(X: np.ndarray) -> list[int]`: matrix multiply + argmax, numpy-only
- `predict_proba(X: np.ndarray) -> list[list[float]]`: softmax over logits, numpy-only
- `n_classes: int`, `n_features: int`

#### Scenario: Standalone inference
- **WHEN** EdgeLoader is instantiated in an environment without scikit-learn
- **THEN** `predict()` runs successfully using only numpy

#### Scenario: Output matches original
- **WHEN** a sample is predicted by both the original classifier and the edge loader
- **THEN** labels match exactly (within floating-point tolerance for proba)

### Requirement: geo_export_for_edge tool
GeoAgent tool SHALL accept optional `key` (default: global classifier). Writes
the export bundle to `output_dir` and registers all output files as artifacts.

## Non-goals

- Quantization (INT8) — reserved for future optimization
- ONNX export — separate spike needed
- GPU acceleration
