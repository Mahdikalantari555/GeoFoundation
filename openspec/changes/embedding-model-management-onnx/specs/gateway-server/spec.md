## Purpose
Add ONNX dense text embeddings, a local model hub scanning `/mnt/data/LocalAI/Models/Embedding` etc, and gateway model-management APIs with auto-download so sovereign retrieval works without manual steps.

## ADDED Requirements

### Requirement: ONNX text embedding backend
The system SHALL support `embedding_backend="onnx"` with an `OnnxTextEmbedder` that produces L2-normalized vectors via onnxruntime+tokenizers, reporting `space_id=text.onnx.<safe-model>.v1`.

#### Scenario: ONNX search parity
- **WHEN** the same 50 fixture texts are embedded via `sentence-transformers` and via `onnx` for model `all-MiniLM-L6-v2`
- **THEN** cosine correlation >0.998 and mean L2 delta <1e-3

#### Scenario: Unknown backend rejected
- **WHEN** `PUT /api/v1/workspace/settings` sets `embedding_backend="bogus"`
- **THEN** it returns 422 `validation` with `detail.available: ["hashing","llama-cpp","sentence-transformers","onnx"]`

### Requirement: Embedding model hub local scan
The hub SHALL scan roots `GEOMEMORY_EMBEDDING_ROOT → workspace.embedding_path → /mnt/data/LocalAI/Models/Embedding → HF cache → workspace/indexes` and list models as `{id, name, backend, path, size_bytes, downloaded, loadable, space_id}`.

#### Scenario: Hub lists LocalAI dir
- **WHEN** `GET /api/v1/models` is called with a scan root `/mnt/data/LocalAI/Models/Embedding` present
- **THEN** it includes an entry for any ST/ONNX model under that root with `downloaded=true`

### Requirement: Model download as background job with auto-download
`POST /api/v1/models/download {model_name, backend}` SHALL enqueue a job (`202`) exposing download progress via `GET /api/v1/jobs/{id}` + SSE `job_progress`. First `build_index`/`search` with `embedding_backend∈{st,onnx}` and no local model SHALL auto-download `st_model_name`/`onnx_model_name` (default `all-MiniLM-L6-v2`) when `offline==false`; when `offline==true` it SHALL return `503 embedding_unavailable` with hint.

#### Scenario: Cold start auto-download
- **WHEN** `POST /api/v1/index/build` is called with `embedding_backend=sentence-transformers` and no model cached and `offline==false`
- **THEN** the job initially reports `status=running, progress~downloading` and eventually `done` with the model `downloaded=true`, and a second build uses the cached model without re-downloading

#### Scenario: Offline guard
- **WHEN** the same call is made with `offline==true` and no local model
- **THEN** it returns `503 embedding_unavailable` with `detail.offline=true` and `detail.hint="set offline=false or pre-download"`

### Requirement: Gateway Doctor embedding summary
`GET /api/v1/doctor` diagnostics SHALL include `embedding: { hub_count, downloaded, active_backend, active_model, active_space_id }` and `GET /api/v1/models` mirrors hub state.

#### Scenario: Doctor shows embedding hub
- **WHEN** Doctor is fetched after hub scan
- **THEN** `diagnostics.embedding.active_backend` matches workspace settings and `diagnostics.embedding.hub_count` ≥ 0
