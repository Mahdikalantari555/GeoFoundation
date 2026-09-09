## Purpose

Experiments with exporting the OLMoEarth v1.2 Nano PyTorch checkpoint to ONNX format to determine whether a lightweight, torch-free runtime path is viable for production use. The spike produces measurable deltas in model size, inference latency, and embedding quality vs. the native torch implementation.

## ADDED Requirements

### Requirement: ONNX export script produces a runnable model
A script `scripts/export_olmoearth_onnx.py` SHALL export the OLMoEarth Nano v1.2 encoder from its `.pth` state dict to an ONNX `.onnx` file and a `tokenizer.json`-compatible representation, using the same input tensor shapes (N, H, W, 1, 12) and patch-size configuration as the native model.

#### Scenario: Export succeeds with valid checkpoint
- **WHEN** the script is run with `--input <path/to/weights.pth>` and `--output <dir>`
- **THEN** an `model.onnx` file and config manifest are written to the output directory

#### Scenario: Export fails on missing checkpoint
- **WHEN** the script is run with a nonexistent `.pth` path
- **THEN** the script exits with code 1 and prints the missing-file path

### Requirement: Quality delta measurement
The spike SHALL compare embeddings produced by the exported ONNX model against the native torch model on a fixed test set of at least 20 satellite image tiles and report the mean cosine distance between paired embeddings.

#### Scenario: Quality delta reported
- **WHEN** the spike comparison script runs on exported and native models
- **THEN** it outputs a CSV or JSON table with per-sample cosine distance and a mean delta

#### Scenario: Acceptance threshold
- **WHEN** mean cosine distance is ≤ 0.02 between native and ONNX embeddings
- **THEN** the spike reports "acceptable quality retention" and recommends ONNX for production consideration

### Requirement: Latency and size benchmark
The spike SHALL measure per-image embedding latency (mean over 50 runs) and ONNX model file size, comparing against the torch native baseline.

#### Scenario: Metrics reported
- **WHEN** the benchmark script completes
- **THEN** it outputs latency (ms), model size (MB), and embedding dimension for both implementations
