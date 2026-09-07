# Tasks — remove-txtai-torch-lightweight-retrieval

## 1. Deps hygiene
- [x] 1.1 `server/pyproject.toml` / `environment.yml` stop depending on `geomemory[ai]`/`[st]`; depend on `geomemory` plain (transitively `onnxruntime` + `sqlite-vec`) — no `torch`/`txtai` in `pipdeptree`
- [x] 1.2 Verify no `txtai`/`sentence_transformers`/`torch` imports remain in `server/src` (behind facades only)
- [x] 1.3 `libs/geomemory` base deps are `onnxruntime` + `tokenizers` + `huggingface-hub` + `sqlite-vec`; `torch` only under `[vision]`

## 2. Doctor diagnostics
- [x] 2.1 `geomemory.services.doctor.doctor_embedding` reports `sqlite_vec` (`installed`, `loadable`, `version`) and `embedding_provider` (`active_provider`, `active_model`, `active_space_id`)
- [x] 2.2 `GET /api/v1/doctor` no longer reports `txtai`; `diagnostics.embedding` + `diagnostics.sqlite_vec` present; `environment.optional_deps` shows `onnxruntime`/`tokenizers`/`sqlite_vec` as canonical

## 3. Docker lightweight
- [x] 3.1 `server/Dockerfile` builds without `torch`/`txtai` layers; installs `onnxruntime` + `sqlite-vec` via `geomemory` base
- [x] 3.2 `docker-compose.yml` `GEOFOND_WORKSPACE=/workspace` single worker invariant holds; image runs `geomemory doctor` + ONNX CPU inference smoke test

## 4. Verification
- [x] 4.1 `conda run -n geospatial pip show geomemory` → Requires: `onnxruntime`, `sqlite-vec` (no torch); `pipdeptree | grep -qiE "torch|txtai"` finds no matches
- [x] 4.2 `conda run -n geospatial pytest server/tests -q` passes without torch installed
- [x] 4.3 `conda run -n geospatial pytest libs/geomemory/tests -q -k "not vision"` passes; `python -c "from geomemory.embeddings.provider import ONNXEmbeddingProvider; print(ONNXEmbeddingProvider().embed(['hello']).shape)"` prints `(1, 384)` via `CPUExecutionProvider`
