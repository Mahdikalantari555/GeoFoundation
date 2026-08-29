# SPEC — Gateway Server API v1

> FastAPI gateway wrapping the public facades of `geomemory` (libs/geomemory)
> and `geoagent` (libs/geoagent). All responses JSON. Prefix `/api/v1`.
> This is the ONLY surface apps may consume.

## Conventions

- Error envelope: `{ "error": { "code": str, "message": str, "detail": any? } }`
  - `409 workspace_not_open` · `404 not_found` (asset/tool/collection)
  - `422 validation` · `503 backend_unavailable` (LLM/embedder down → drives
    abstention/guardrail UI states)
- Long operations (ingest, index build, benchmark, playbook runs) return
  `202 { "job_id": str }` → `GET /jobs/{id}` → `{status: queued|running|done|error, progress?, result?, error?}`.
- SSE endpoints: `text/event-stream` with named events; abortable by client.
- Active workspace: server-side singleton behind a write lock
  (`state.py`). One gateway = one workspace at a time.

## Health & events

| Method | Route | Notes |
|---|---|---|
| GET | `/health` | `{status, workspace: closed|open, path?, llm: {provider, configured, reachable?}}` |
| GET | `/api/v1/events` | SSE: `asset_created`, `collection_created`, `job_progress` |

## Workspace

| Method | Route | Body → Maps to |
|---|---|---|
| POST | `/workspace/create` | `{path, name, ...}` → `GeoMemory.create` under `path/<name>/` |
| POST | `/workspace/open` | `{path}` → `GeoMemory.open` (auto-detects a nested workspace subdir) |
| POST | `/workspace/close` | → `ws.close()` |
| GET | `/workspace` | status + `ws.settings` |
| PUT | `/workspace/settings` | partial config → `ws.update_settings` (**422 if `llm_api_key_env` is in the body**) |
| GET | `/workspace/stats` | `ws.stats()` |

Config fields: `name, language(en|fa), offline, batch_size, model_path,
embedding_path, vision_path` + LLM compute: `llm_provider (api|llamacpp,
api = default), llm_api_base_url, llm_model_id, llm_context_window,
llm_api_key_env`. The API key itself is **server-env-only** (read at call
time from the named env var, e.g. `GEOMEMORY_LLM_API_KEY`); it is never
accepted from clients, never persisted, never returned by any endpoint.
`PUT /workspace/settings` rejects any request that attempts to set
`llm_api_key_env` with HTTP 422 — clients configure only the *env var name*,
and the gateway seeds `llm_api_base_url` / `llm_model_id` from
`GEOMEMORY_LLM_API_BASE_URL` / `GEOMEMORY_LLM_MODEL_ID` in the server env when
a workspace is created or opened. Workspace files are stored nested under
`path/<name>/` so multiple workspaces can share a parent directory.

## Collections

| Method | Route | Maps to |
|---|---|---|
| GET | `/collections` | `ws.list_collections()` |
| POST | `/collections` | `ws.create_collection(name, description?)` |
| GET | `/collections/{id}` | `ws.get_collection` |
| DELETE | `/collections/{id}` | `ws.archive_collection` |

## Ingest

| Method | Route | Notes |
|---|---|---|
| POST | `/ingest` | multipart (file, collection_id, index_after?) → `ws.ingest`, 202 job |
| POST | `/ingest/bytes` | JSON base64 → same pipeline |

Job result carries `skipped: true` on SHA-256 dedup — UI shows the dedup banner.
Accepted types: pdf, txt, md, csv, py, ipynb, tif/tiff(geotiff), geojson, gpkg.
DOCX disabled (loader is a known geomemory gap).

## Search & Ask

| Method | Route | Body |
|---|---|---|
| POST | `/search` | `{query, mode: sparse|dense|hybrid, top_k?, top_n?, collections?: [id], spatial?: {op, bbox?, geometry_id?, distance_m?}, temporal?: {field, from?, to?}, sensor?: [str]}` → `ws.search` |
| POST | `/ask` | `{question, mode: grounded_qa|research|code, collections?, filters?}` → `ws.ask` |

Result shapes come straight from the libs' Pydantic models
(`SearchHit{ id, score, sparse_score, dense_score, text, locator, metadata }`,
`QAResult{ answer, citations[{locator, segment_id, claim_span}], abstained, abstain_reason? }`).

## Assets

| Method | Route | Maps to |
|---|---|---|
| GET | `/assets?collection_id=` | `ws.list_assets` |
| GET | `/assets/{id}` | `ws.inspect` (asset + revision + segments + scenes + layers + observations) |

## Index & images

| Method | Route | Maps to |
|---|---|---|
| POST | `/index/build` | `{space_id}` → job → `ws.build_index` |
| POST | `/index/rebuild` | `{space_id}` → job → `ws.rebuild_index` |
| POST | `/images/search` | experimental: `ws.search_images` (vision) |

Spaces: `text.nomic.v1` (default), `text.hash.v1` (offline).

## Feedback & eval

| Method | Route | Maps to |
|---|---|---|
| POST | `/feedback` | `ws.record_feedback(event)` |
| GET | `/feedback/review-queue` | `ws.get_review_queue()` |
| POST | `/feedback/review/{example_id}` | `{accept, reviewer_id?}` → `ws.review_example` |
| POST | `/feedback/export` | `{task_type}` → JSONL file download |
| POST | `/eval/benchmark` | multipart jsonl + config → job → `ws.run_benchmark` |

## Doctor

Environment diagnostics run **without** an open workspace (they never return
409). `GET /doctor` reports a graceful `closed` status when no workspace is
active; `GET /doctor/llm` falls back to the gateway's default LLM health
(env var + provider/model defaults) so the key-configuration state is always
visible.

| Method | Route | Maps to |
|---|---|---|
| GET | `/doctor` | `doctor_environment()` + workspace report (or `closed`) |
| GET | `/doctor/environment` | `doctor_environment()` |
| GET | `/doctor/workspace?path=` | `doctor_workspace(path)` |
| GET | `/doctor/roundtrip?path=` | `doctor_workspace_open(path)` |
| GET | `/doctor/llm` | LLM backend probe: provider, key configured, base URL, model id, context window |

## Agent (geoagent)

| Method | Route | Notes |
|---|---|---|
| POST | `/agent/chat` | SSE: `token`, `tool_run`, `turn_done` (answer + citations [S#]), `guardrail` (budget failure) |
| GET | `/agent/conversations` | session list |
| GET | `/agent/conversations/{id}` | full turn timeline |
| GET | `/agent/tools` | live manifest (built-in + plugins + playbooks) |
| POST | `/agent/tools/{name}/call` | typed args, returns renderable result (json/table/geojson/map.png path) |
| GET | `/agent/playbooks` | playbook list |
| POST | `/agent/playbooks` | save-from-conversation |
| POST | `/agent/playbooks/{id}/run` | SSE progress |
| GET | `/agent/files/*` | sandboxed artifact serving — root = active workspace `runs/`; path-normalized, no `..` |
| GET | `/agent/farms` · POST `/agent/farms/{id}/report` | registry + stress report (report.md, stats.csv, map.png, evidence pack with data gaps → abstention UI) |

## Server layout

```
server/
├── pyproject.toml            # fastapi, uvicorn, python-multipart; editable path deps on ../libs/*
└── src/geofront_api/
    ├── main.py               # app factory, CORS, routes, /files sandbox mount
    ├── state.py              # active workspace holder + asyncio write lock
    ├── schemas.py            # request DTOs (responses = libs' models)
    ├── jobs.py               # background job registry + progress
    └── routers/              # workspace, collections, ingest, search, ask,
                              # assets, index, feedback, eval, doctor,
                              # events, agent/{chat,tools,playbooks,files,farms}
```
