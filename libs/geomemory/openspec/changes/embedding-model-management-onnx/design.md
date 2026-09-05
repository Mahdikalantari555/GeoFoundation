## Context

`WorkspaceSettings` already has `embedding_backend ∈ {hashing, llama-cpp, sentence-transformers}`, `st_model_name`, and env override `GEOMEMORY_ST_MODEL`. `SentenceTransformerEmbedder` (`embeddings/sentence_transformer.py`) does `SentenceTransformer(model_name)` which by default writes to `~/.cache/huggingface`; `factory.py` picks backend. No ONNX, no hub, no listing endpoint. Doctor has `core_deps/optional_deps` but no embedding model inventory. Web Settings exposes `embedding_path` as freeform path, not a model catalog. Default dev dir `/mnt/data/LocalAI/Models/Embedding/V1.2_Nano` is a vision-style `weights.pth` not an ST model — scan must distinguish backends and not confuse vision embedding.

## Goals / Non-Goals

**Goals:**
- Dense text embeddings work via either ST (torch) or ONNX (CPU light) with identical cosine semantics.
- Hub scans known local roots including `/mnt/data/LocalAI/Models/Embedding` and reports downloadable vs downloaded.
- `all-MiniLM-L6-v2` auto-downloads on first use when `offline==False` (no manual CLI).
- Web shows available models and allows downloading other HF models (e.g. `BAAI/bge-small-en-v1.5`) with progress.
- Doctor reports embedding hub + resolved model.

**Non-Goals:**
- Vision ONNX (text only this change; vision path separate).
- Qdrant server auto-provision (handled elsewhere).
- Re-training or fine-tuning embeddings.

## Decisions

- **ONNX backend via onnxruntime+tokenizers, not optimum**: `optimum[onnxruntime]` is heavy; minimal direct session+tokenizer is lighter and makes docker image small. Alternate — adopt `sentence-transformers[onnx]` — would tie versioning; rejected for image size. Decision: implement `OnnxTextEmbedder` that loads `tokenizer.json` + `model.onnx` (or `onnx/model.onnx`) via `onnxruntime.InferenceSession`, padding+attention mask, mean pool, L2 normalize. Fallback to fetch via `huggingface_hub` if missing, using `onnx-community/*-ONNX` namespace when `backend==onnx`.
- **Hub over eager registry**: hub is filesystem scan, not DB. Rationale: models live on filesystem; scanning is cheap and source of truth. Stores metadata in memory; no migration. Roots priority: env `GEOMEMORY_EMBEDDING_ROOT` → `workspace.embedding_path` (if dir) → `/mnt/data/LocalAI/Models/Embedding` (dev) → `~/.cache/huggingface/hub` → `workspace/indexes`. Vision dir excluded unless `config.json` indicates text model.
- **Auto-download as background job**: gateway must not block event loop on `snapshot_download`. `POST /models/download` → `jobs.submit("model_download", lambda: hub.download(...))` with progress callback `job.update(progress=...)`. `SentenceTransformerEmbedder._load` in non-job context still does inline download but guarded by `offline` check and timeout; index/search routes prefer enqueuing if missing and `offline==False` rather than erroring.
- **Gateway model id normalization**: `st_model_name` / `onnx_model_name` stored verbatim (HF id). `space_id` derived `text.st.<safe>.v1` or `text.onnx.<safe>.v1` so embedding spaces stay isolated per modality+model invariant.
- **Size reporting**: hub computes `size_bytes` as sum of relevant files (not entire hf cache blob). UI shows humanized size.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| ONNX parity drift | Golden test: embed 50 fixture sentences via ST vs ONNX, cosine correlation >0.998 and mean delta <1e-3. |
| HF rate limit / offline CI | Tests stub `hub.download` and use small local fixture; e2e only hits hub in optional integration with `HF_ENDPOINT` mock. |
| `/mnt/data/LocalAI/Models/Embedding` not present in CI/docker | Scan tolerates missing root; CI uses temp dir hub. |
| Download concurrency | Hub file lock per model (pid file); second concurrent download reuses in-flight job id. |

## Verification

- Lib tests: `tests/embeddings/test_onnx_parity.py`, `tests/embeddings/test_hub_scan.py`, `tests/embeddings/test_auto_download_offline_guard.py`.
- Server tests: `server/tests/test_models.py` (GET /models lists hub, POST /models/download 202+progress, PUT settings embedding_backend validation, index auto-download stub).
- Web tests: Vitest for Settings embedding section (select backend, download button disabled when offline, progress bar), Index hub list.
- Manual: `GEOMEMORY_EMBEDDING_ROOT=/tmp/emb conda run -n geospatial python -m geomemory doctor` shows hub; UI download of `all-MiniLM-L6-v2` with SSE progress.
