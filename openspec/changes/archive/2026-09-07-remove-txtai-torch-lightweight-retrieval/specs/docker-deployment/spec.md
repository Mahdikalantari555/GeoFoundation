## Purpose
Docker images become lightweight and CPU-only via ONNX + sqlite-vec, with measurable size/startup improvement.

## ADDED Requirements

### Requirement: Lightweight image (no torch/txtai)
The default `Dockerfile` SHALL build a runnable GeoFoundation stack without `torch` or `txtai` in the image layers; it SHALL include `onnxruntime`, `tokenizers`, `sqlite-vec`, and `huggingface-hub` for the `Xenova/all-MiniLM-L6-v2` quantized model.

#### Scenario: Image size regression gate
- **WHEN** `docker build -t geofoundation:test .` completes
- **THEN** `docker images geofoundation:test --format "{{.Size}}"` is at least 1.5 GB smaller than the last pre-refactor baseline image and `docker run --rm geofoundation:test python -c "import geomemory; print(geomemory.__version__)"` succeeds without importing `torch`

#### Scenario: CPU-only inference
- **WHEN** the container runs `python -c "from geomemory.embeddings.provider import ONNXEmbeddingProvider; print(ONNXEmbeddingProvider().embed(['hello']).shape)"`
- **THEN** it prints `(1, 384)` using `CPUExecutionProvider` without requiring CUDA or `nvidia-smi`
