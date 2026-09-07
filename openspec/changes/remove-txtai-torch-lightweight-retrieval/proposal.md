# Proposal: remove-txtai-torch-lightweight-retrieval (GeoFoundation gateway)

Thin gateway companion to `libs/geomemory` change `remove-txtai-torch-lightweight-retrieval`. The gateway imports only the public `geomemory` facade, so its code change is minimal — the substance is in `libs/geomemory`. This proposal records the gateway/docker follow-through.

## Why

`server` and Docker images currently transitively install `torch`/`txtai` via `geomemory[ai]`/`geomemory[st]`. That inflates the image by 2–3 GB, slows CI, and prevents Colab/serverless use. After `libs/geomemory` cuts the graph (ONNX + sqlite-vec), the gateway must stop requesting the heavy extras and surface the new lightweight defaults.

## What Changes

- **Deps**: `server/pyproject.toml` / `requirements.txt` / `environment.yml` stop depending on `geomemory[ai]` or `[st]`; depend on `geomemory` (plain) or `geomemory[onnx,sqlite-vec]` (canonical). No `torch`/`txtai` in the gateway's `pipdeptree`.
- **Code**: no `txtai`/`sentence_transformers` imports remain (they were already absent behind facades — verify). `servers/services/*` continue to call `GeoMemory` facade only. Doctor's diagnostics now include `sqlite_vec` + `embedding_provider`; `txtai` rows removed.
- **Docker**: `Dockerfile` / `docker-compose.yml` base image installs `onnxruntime` + `sqlite-vec` (CPU) and drops `torch`/`txtai` layers. Add image-size regression gate (`docker images` ≥1.5 GB smaller than baseline).
- **Web**: `WorkspaceSettings` schema may gain `embedding_provider` / `onnx_model_name` (if not already in `embedding-model-management-onnx`). Regenerate client `pnpm gen:api` and verify Doctor/Settings/Index pages show `embedding_provider` and `sqlite_vec` status. (If web change is deferred, note as follow-up.)
- **Verification**: `pip install geomemory` in clean venv → no `torch`/`txtai`; `pytest server/tests -q` passes without torch installed; `docker build` succeeds and runs `geomemory doctor` + search smoke test.

## Capabilities

### Modified Capabilities
- `gateway-server`: dependency graph cleaned of `torch`/`txtai`; Doctor diagnostics reflect new embedding/vector stack.
- `docker-deployment`: base image lightweight (ONNX + sqlite-vec, no torch).

## Impact

- **Code**: `server/pyproject.toml`, `server/requirements*.txt`, `environment.yml`, `Dockerfile`, `docker-compose.yml`, `server/src/geofront_api/services/doctor.py` (if needed), docs.
- **Risks**: none beyond the lib migration already covered; gateway risk is stale `pyproject.toml` extra still pulling torch — mitigated by `pipdeptree` CI gate.
