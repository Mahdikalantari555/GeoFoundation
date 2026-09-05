## 1. Lib — ONNX embedder + hub

- [ ] 1.1 Create `libs/geomemory/src/geomemory/embeddings/onnx_text.py` (`OnnxTextEmbedder`: tokenizer+session, mean pool, L2 norm, `space_id=text.onnx.*`, e5 prefix). Add `geomemory[onnx]` extra.
- [ ] 1.2 Extend `WorkspaceSettings` (`onnx_model_name`, `embedding_backend` allow `onnx`) + `embeddings/factory.py` routing + `core/config.ENV_OVERRIDES` for `GEOMEMORY_ONNX_MODEL`
- [ ] 1.3 Create `embeddings/hub.py` (`EmbeddingModelHub.scan`, priority roots including `/mnt/data/LocalAI/Models/Embedding`, `download` with `huggingface_hub.snapshot_download`, progress callback, file lock). Unit tests for scan+offline guard.
- [ ] 1.4 Auto-download wiring in `SentenceTransformerEmbedder._load` + `OnnxTextEmbedder._load` + `services/index_service.py` (attempt inline download when offline false else 503)

## 2. Server — model management API

- [ ] 2.1 Add `server/src/geofront_api/routers/models.py`: `GET /models`, `POST /models/download` (202 job), `GET /models/{id}/status`. Wire `jobs` + SSE. Tests for list/download 202+progress, validation.
- [ ] 2.2 Extend `routers/workspace.py` settings to accept `embedding_backend`/`st_model_name`/`onnx_model_name` with 422 `available`; extend `routers/index.py` to trigger auto-download fallback before build; extend `routers/doctor.py` `diagnostics.embedding` summary.

## 3. Web — settings embeddings + index hub

- [ ] 3.1 Settings page: embeddings subsection (backend select, model picker from `GET /models`, `space_id` + size badges, Download button → `POST /models/download` → job progress bar, offline guard disabled state). `PUT /settings` wiring + `pnpm gen:api`.
- [ ] 3.2 Index page: hub list table with per-row Download + progress, active backend/model banner, Build/Rebuild buttons that gracefully trigger auto-download when missing.
- [ ] 3.3 Doctor page: embedding row (hub_count, active_model, fallback status) in diagnostics section.

## 4. Verification

- [ ] 4.1 Lib: `conda run -n geospatial pytest libs/geomemory/tests/embeddings -q` parity test `onnx vs st` >0.998; hub scan temp fixture; `ruff`/`mypy --strict`
- [ ] 4.2 Server: `conda run -n geospatial pytest server/tests/test_models.py server/tests/test_index_auto_download.py -q`
- [ ] 4.3 Web: `pnpm gen:api && pnpm lint && pnpm build && pnpm test` + manual `GEOMEMORY_EMBEDDING_ROOT=/tmp/emb pnpm dev` — download minilm shows progress and subsequent search uses cached model
