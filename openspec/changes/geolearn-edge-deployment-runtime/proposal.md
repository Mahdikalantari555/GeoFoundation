## Why

GeoLearn must run on resource-constrained platforms — CPUs, mobile devices,
UAVs, and edge computing nodes used in agricultural field operations. The
current classifier state is stored as a joblib pickle, which requires the
full scikit-learn stack to deserialize. For true edge deployment, we need
a lighter serialization format and a minimal runtime that can load predictions
without the full library.

## What Changes

1. Add `export_for_edge(output_dir)` method to `OnlineClassifier`: serializes
   the classifier to a standalone JSON+numpy bundle (weights as base64,
   classes as string array) that can be loaded without scikit-learn.
2. Add `EdgeLoader` class: a minimal predictor that loads the JSON bundle and
   runs inference using only numpy (no sklearn dependency at runtime).
3. Add `geo_export_for_edge(key?, output_dir)` tool in GeoAgent for one-click
   deployment package generation.
4. Include a small `README.md` in the exported bundle describing the format.

## Capabilities

### New Capabilities
- `geolearn-edge-deployment-runtime`: portable classifier export + numpy-only loader.

## Impact

- Export format is a custom JSON schema (documented in the bundle).
- `EdgeLoader` is ~50 lines, zero external deps beyond numpy.
- The full scikit-learn classifier remains the primary form; edge bundle is
  a derived artifact.
- No changes to existing training or prediction paths.
