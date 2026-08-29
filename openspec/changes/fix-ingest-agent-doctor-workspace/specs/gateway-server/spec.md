## Purpose
Harden the gateway facade so ingest, agent chat, doctor diagnostics, workspace defaults, and error surfacing never fail silently, with typed contracts that the web app can render reliably.

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Uniform error envelope
All error responses SHALL use `{error: {code, message, detail?}}` and non-2xx responses SHALL include an `X-Request-ID` header whose value also appears as `detail.request_id` on 500. Validation errors SHALL include `detail` as the structured field-error array. 500 SHALL never leak a stack to clients.

#### Scenario: 500 carries request_id
- **WHEN** an unhandled exception occurs
- **THEN** the response is 500 with `error.code=internal_error`, `error.detail.request_id` present, and header `X-Request-ID` matching `detail.request_id`, and server log contains the same id

### Requirement: Background jobs
Long operations SHALL expose error terminals. The ingest job result on failure SHALL set `error` and `job_progress` SHALL emit an `error` status that polling `GET /api/v1/jobs/{id}` surfaces.

#### Scenario: Failed ingest surfaced
- **WHEN** `ws.ingest` raises inside a job
- **THEN** `GET /jobs/{id}` eventually reports `status=error` with `error.code` and `detail`, and an SSE `job_progress` event with `status=error` is published

### Requirement: Sandboxed artifact serving
Unchanged, but error for traversal/missing file SHALL use the uniform envelope (404 `asset_not_found` / `not_found`) with request_id.

## ADDED Scenarios for existing Requirements

### Requirement: HTTP facade over public libraries — Ingest validation
- **WHEN** `POST /api/v1/ingest` receives a filename with unsupported extension
- **THEN** it returns 422 `unsupported_format` with `detail.accepted: string[]` and `detail.received: string`
- **WHEN** an upload exceeds `MAX_INGEST_BYTES` (500MB)
- **THEN** it returns 413 `payload_too_large` with `detail.size_bytes` and `detail.limit_bytes`

### Requirement: Agent chat SSE contract
- **WHEN** `POST /api/v1/agent/chat` is called without an open workspace or with uninitialized AgentService
- **THEN** it returns 409 `agent_not_ready` with actionable message
- **WHEN** `POST /api/v1/agent/chat` streams successfully
- **THEN** events arrive in order `conversation → thinking → (tool_start/tool_end)* → message* → done`, and on failure an `error` event (`code/message/detail`) is emitted before `done`
- **WHEN** the client aborts the stream
- **THEN** the server stops the `to_thread` task promptly and no unhandled exception propagates
