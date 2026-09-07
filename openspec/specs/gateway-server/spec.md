# gateway-server Specification

## Purpose
TBD - created by archiving change add-gateway-server. Update Purpose after archive.

## Requirements

### Requirement: HTTP facade over public libraries
The server SHALL expose `/api/v1` endpoints that call only the public facades of `geomemory` and `geoagent`, and SHALL NOT import any library internal module, and its transitive graph SHALL NOT contain `txtai`, `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, or `safetensors` when installed without `[vision]`; it SHALL satisfy this via `pipdeptree` in CI.

#### Scenario: Facade-only imports
- **WHEN** the server package is inspected for imports
- **THEN** every `geomemory`/`geoagent` import resolves to a public API path

#### Scenario: No torch in gateway env
- **WHEN** `pip install geofront-api` (or `server` deps) is performed in a clean env
- **THEN** `pipdeptree | grep -qiE "torch|txtai"` finds no matches

### Requirement: Workspace state machine
The server SHALL hold at most one active workspace (create/open/close),
serialize write operations behind an async lock, and run as a single worker.
Requests requiring a workspace SHALL fail with `409 workspace_not_open`
when none is active. `GET /api/v1/doctor` and `GET /api/v1/doctor/llm` are
exceptions: they are environment diagnostics and SHALL return `200` with a
`closed` status (or gateway LLM defaults) instead of `409`.

#### Scenario: Search without workspace
- **WHEN** `POST /api/v1/search` is called and no workspace is open
- **THEN** the response is `409` with the error envelope

### Requirement: Background jobs
Long operations (ingest, index build/rebuild, benchmark, playbook runs) SHALL return `202 {job_id}` and report progress via `GET /api/v1/jobs/{id}` until terminal status; job results SHALL surface library outcomes including ingest dedup (`skipped: true`). On failure the job SHALL set `error` and `job_progress` SHALL emit an `error` status that polling `GET /api/v1/jobs/{id}` surfaces.

#### Scenario: Ingest job lifecycle
- **WHEN** a file is uploaded to `POST /api/v1/ingest`
- **THEN** the response is `202` with a job id
- **AND** polling `GET /jobs/{id}` transitions queued → running → done with the ingest result (asset_id, segment_count, or skipped flag)

#### Scenario: Failed ingest surfaced
- **WHEN** `ws.ingest` raises inside a job
- **THEN** `GET /jobs/{id}` eventually reports `status=error` with `error.code` and `detail`, and an SSE `job_progress` event with `status=error` is published

### Requirement: SSE event stream
The server SHALL stream `asset_created`, `collection_created`, and job
progress events over `GET /api/v1/events` for UI cache invalidation.

#### Scenario: Event after ingest
- **WHEN** an ingest job completes
- **THEN** an `asset_created` event is emitted on the SSE stream

### Requirement: Hybrid LLM compute, secrets handling
The server SHALL default LLM selection to the API provider
(OpenAI-compatible), support `llamacpp` as local fallback, and read API keys
from server environment variables (name from `llm_api_key_env`, default
`GEOMEMORY_LLM_API_KEY`). The API key MAY be set via `PUT /api/v1/workspace/settings` field `llm_api_key`; when provided the gateway SHALL set `os.environ[effective_key_env]` at runtime (never persisted to the workspace DB) and SHALL never return the key value in any response. The env var name `llm_api_key_env` MAY be updated via settings. Unavailable backends SHALL produce `503` errors or library abstention results, never stack traces. The gateway SHALL seed `llm_api_base_url` and `llm_model_id` from the server env (`GEOMEMORY_LLM_API_BASE_URL` / `GEOMEMORY_LLM_MODEL_ID`) when a workspace is created or opened, so a deployment can configure the LLM connection without editing stored settings.

#### Scenario: Key never crosses the wire
- **WHEN** any endpoint's response payload is inspected
- **THEN** the API key value does not appear

#### Scenario: Key settable through settings
- **WHEN** `PUT /api/v1/workspace/settings` receives a body containing `llm_api_key`
- **THEN** the server sets the env var named by `llm_api_key_env` (or `GEOMEMORY_LLM_API_KEY` by default) to that value at runtime, does not persist the key to the workspace DB, and returns `200` with updated settings that do not contain the key

#### Scenario: LLM probe
- **WHEN** `GET /api/v1/doctor/llm` is called
- **THEN** it reports provider, key configured (bool), base URL, model id,
  and context window without leaking the key, and works without an open
  workspace (falling back to gateway defaults)

### Requirement: Sandboxed artifact serving
`GET /api/v1/agent/files/*` SHALL serve only files under the active workspace's `runs/` directory, normalizing paths and rejecting traversal. Errors SHALL use the uniform envelope (404 `asset_not_found` / `not_found`) with `X-Request-ID`.

#### Scenario: Traversal rejected
- **WHEN** a request path contains `..` or escapes the runs root
- **THEN** the response is `404`

### Requirement: Uniform error envelope
All error responses SHALL use `{error: {code, message, detail?}}` and non-2xx responses SHALL include an `X-Request-ID` header whose value also appears as `detail.request_id` on 500. Validation errors SHALL include `detail` as the structured field-error array. 500 SHALL never leak a stack to clients.

#### Scenario: Validation failure
- **WHEN** a request body fails schema validation
- **THEN** the response is `422` with code `validation`

#### Scenario: 500 carries request_id
- **WHEN** an unhandled exception occurs
- **THEN** the response is 500 with `error.code=internal_error`, `error.detail.request_id` present, and header `X-Request-ID` matching `detail.request_id`, and server log contains the same id

### Requirement: Doctor reflects lightweight stack
`GET /api/v1/doctor` diagnostics SHALL stop reporting `txtai` and SHALL report `embedding_provider` (active provider, space_id, dimension) and `sqlite_vec` (`installed`, `loadable`, `version`) alongside existing LLM/Qdrant/Vision checks.

#### Scenario: Doctor after refactor
- **WHEN** `GET /api/v1/doctor` is called with `sqlite-vec` installed
- **THEN** response contains `diagnostics.sqlite_vec.loadable == true` and `diagnostics.embedding.active_provider == "onnx"` and no `txtai` key

### Requirement: Workspace default root and path normalization
The system SHALL default the workspace root to the gitignored `Workspaces` directory (`/mnt/data/Projects/RS/Thesis_Project/GeoFoundation/Workspaces` in dev, `/workspace` in containers, overridable via `GEOFOND_WORKSPACE`) and SHALL auto-create parent directories on create.

#### Scenario: Create with empty path uses default
- **WHEN** `POST /api/v1/workspace/create` is called with `path=""` or omitted
- **THEN** the workspace is created under `GEOFOND_WORKSPACE/<name>/` and response `path` equals that resolved path

#### Scenario: Gitignore covers canonical dir
- **WHEN** `.gitignore` is inspected
- **THEN** it contains `Workspaces/` (and not just variants) so `Workspaces/**` is never committed

### Requirement: Typed doctor diagnostics (no object-in-checks)
`GET /api/v1/doctor` SHALL return `{ environment, workspace: {ok, checks: Record<string, bool|string|number|null>}, workspace_open: {ok, checks: ...}, diagnostics: { llm, qdrant, pdf_parser, vision } }` where `checks` never contains nested objects. Rich diagnostics SHALL live only in `diagnostics`.

#### Scenario: Doctor checks are flat
- **WHEN** `GET /api/v1/doctor` is fetched
- **THEN** every value in `workspace.checks` and `workspace_open.checks` is `boolean | string | number | null`, and `diagnostics.llm.provider` etc are typed objects

#### Scenario: LLM probe flat
- **WHEN** `GET /api/v1/doctor/llm` is fetched
- **THEN** it returns `{ provider, key_env, key_configured, base_url, model_id, context_window }` with primitives only
