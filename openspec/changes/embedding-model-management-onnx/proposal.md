# Proposal: embedding-model-management-onnx

## Why

GeoFoundation promises data-sovereign retrieval but model management is ad-hoc:

- Embedding backends are disjoint: `hashing` (offline stub) and `sentence-transformers` (torch) require manual `pip install geomemory[st]` and manual model download. The canonical dev embedding cache `/mnt/data/LocalAI/Models/Embedding` (contains `V1.2_Nano/`) is not read by the gateway. Users cannot see which models are available.
- Cold start is broken: first search/build without a local model should auto-download `sentence-transformers/all-MiniLM-L6-v2` (spec default `st_model_name`) but currently just errors 503 — no UX for download progress, no background job.
- No ONNX path exists in `geomemory`. OnnxRuntime would give a light, CPU-friendly dense backend suitable for docker images and for offline sovereign deploy without torch, complementing the existing `llama-cpp` embedding path.
- Settings/UI gap: `WorkspaceSettings.st_model_name` + `embedding_backend` exist but Doctor/Index pages do not list available embedding models, their size/state, or allow switching backend per workspace without editing YAML.

## What Changes

### Geomemory ONNX backend
- Add `libs/geomemory/src/geomemory/embeddings/onnx_text.py` under a new extra `geomemory[onnx]` (`onnxruntime>=1.18`, `tokenizers>=0.15`, `huggingface-hub>=0.23`). Interface matches `SentenceTransformerEmbedder` (`space_id`, `embed`, `embed_query`, `embed_batch`), with tokenizer+ONNX session pooling, L2-normalized outputs, e5 prefix handling reused.
- Register `embedding_backend="onnx"` in `WorkspaceSettings` alongside `hashing | llamacpp | sentence-transformers`, and `onnx_model_name` field (default `sentence-transformers/all-MiniLM-L6-v2` ONNX export or `onnx-community/all-MiniLM-L6-v2-ONNX`). Factory `embeddings/factory.py` routes to ONNX when selected.
- ONNX models are stored under `indexes/text.onnx.<safe-model>.v1` (embedding space isolated per modality invariant stays).

### Local model hub + auto-download
- Introduce `EmbeddingModelHub` in `libs/geomemory/src/geomemory/embeddings/hub.py` that scans roots in priority order: `GEOMEMORY_EMBEDDING_ROOT` env → `WorkspaceSettings.embedding_path` → `/mnt/data/LocalAI/Models/Embedding` → `~/.cache/huggingface` → workspace `indexes/`. Scans for `config.json` / `model.onnx` / `pytorch_model.bin` / `sentence_bert_config.json` and reports `{name, path, size_bytes, backend, downloaded, loadable}`.
- Auto-download: `SentenceTransformerEmbedder._load` and `OnnxTextEmbedder._load` first consult hub; if missing and `offline==False`, lazily download via `huggingface_hub.snapshot_download` (or `sentence_transformers` auto-fetch) under `HF_HOME`/`GEOMEMORY_EMBEDDING_ROOT` with progress callbacks. Gateway wraps this as a background job (`POST /api/v1/models/download`) so cold start does not block HTTP workers; `GET /api/v1/models` lists hub entries.
- Default guarantee: `text.st.all-MiniLM-L6-v2.v1` (minilm) auto-downloads on first `build_index`/`search` when no local model present and offline false — no manual CLI step required. Gateway Doctor reports embedding hub stats and current model resolution.

### Gateway model-management API
- `GET /api/v1/models` → `[{id, name, backend, path, size_bytes, downloaded, loadable, space_id}]` (threadpool, reads hub).
- `POST /api/v1/models/download { model_name, backend: st|onnx }` → 202 `job_id` (background `snapshot_download`), progress via `GET /api/v1/jobs/{id}` + SSE `job_progress`.
- `GET /api/v1/models/{id}/status` convenience.
- `PUT /api/v1/workspace/settings` now accepts `embedding_backend` + `st_model_name` / `onnx_model_name` with validation (unknown model → 422 with `detail.available`).
- Index build honors current `embedding_backend` and auto-download if needed; failure surfaces as 503 `embedding_unavailable` (not 500).

### Web model-management UI
- New **Settings → Embeddings** section (extends existing Settings form): backend selector (hashing/st/onnx/llamacpp), model name picker (populated from `GET /models`), size and downloaded badge, "Download" button (triggers `POST /models/download` → job progress bar), current space_id display. When offline true, download button disabled with hint.
- **Index page**: shows active embedding backend/model, hub list with download actions, and build/rebuild buttons that trigger auto-download fallback when needed.
- **Doctor page**: adds row "embedding models" with hub summary (count, active model, fallback status).

## Capabilities

### New Capabilities
- `embedding-hub`: Local scan + download orchestration for sentence-transformers and ONNX dense text embeddings, hub listing.

### Modified Capabilities
- `gateway-server`: new `GET /api/v1/models`, `POST /api/v1/models/download`, settings extension for embedding backend/model, index auto-download, Doctor embedding summary.
- `web-app`: Settings embeddings section + model download progress, Index page model hub, Doctor embedding row.

## Impact

- **Code**: `libs/geomemory/src/geomemory/embeddings/{onnx_text.py,hub.py,factory.py,__init__.py}`, `core/models.py` (`onnx_model_name`), `services/index_service.py`, `server/routers/{models,workspace,index,doctor}.py`; `apps/web/src/features/{settings,index,doctor}` + `apps/web/src/api/*`.
- **APIs**: new `/api/v1/models` family (additive); `/workspace/settings` extended with `embedding_backend` enum; no breaking change to existing search/ask contracts.
- **Deps**: new optional `geomemory[onnx]` (onnxruntime, tokenizers, huggingface-hub). Docker images optionally include `onnxruntime` (CPU) for light path vs torch.
- **Risks**: ONNX tokenizer parity with sentence-transformers (must verify cosine parity ±1e-3 on fixture). Download via hf hub needs network; offline workspaces must fail gracefully (503 with `offline` hint, not silent). Hub scanning `/mnt/data/LocalAI/Models/Embedding` must not assume writable — downloads go to `GEOMEMORY_EMBEDDING_ROOT` or `~/.cache`.
