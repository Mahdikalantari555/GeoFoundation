## Purpose
Expose embedding model inventory and controls in the web app so users can see, select, and download ST/ONNX models (including auto minilm) without CLI.

## ADDED Requirements

### Requirement: Settings embeddings section
Settings SHALL have an Embeddings subsection showing backend selector (`hashing|sentence-transformers|onnx|llama-cpp`), model name picker populated from `GET /api/v1/models`, current `space_id`, size badges, and a Download button that enqueues `POST /api/v1/models/download` with a progress bar. When `offline==true`, Download SHALL be disabled with explanatory hint. Saving SHALL call `PUT /api/v1/workspace/settings` with `embedding_backend` + model field.

#### Scenario: Switch to ONNX
- **WHEN** user selects `onnx` and model `sentence-transformers/all-MiniLM-L6-v2` and saves
- **THEN** a `PUT /settings` with `{embedding_backend:"onnx", onnx_model_name:"sentence-transformers/all-MiniLM-L6-v2"}` succeeds and refresh shows `space_id=text.onnx.sentence-transformers-all-MiniLM-L6-v2.v1`

#### Scenario: Download while offline disabled
- **WHEN** workspace `offline==true` and user views Settings Embeddings
- **THEN** the Download button is disabled and a message "Downloads require offline=false" is visible

### Requirement: Index page model hub
Index SHALL list hub models (`name, backend, size, downloaded` badges) with Download actions per undownloaded entry and a progress indicator for in-flight download jobs.

#### Scenario: Hub download progress
- **WHEN** user clicks Download on an undownloaded model from Index
- **THEN** a `202` job id appears with a progress bar that updates via `job_progress` SSE/poll until `done`

### Requirement: Download other HF models
The UI SHALL allow typing any HF model id (e.g. `BAAI/bge-small-en-v1.5`) into the model picker or an "Add custom model" field, validate via `POST /models/download`, and after success appear in the `GET /models` list.

#### Scenario: Custom model
- **WHEN** user enters `BAAI/bge-small-en-v1.5` with backend `st` and downloads
- **THEN** after job `done`, `GET /models` lists it with `downloaded=true` and Settings picker includes it
