# gateway-server Specification

## Purpose
TBD - created by archiving change add-gateway-server. Update Purpose after archive.

## Requirements

### Requirement: HTTP facade over public libraries
The server SHALL expose `/api/v1` endpoints that call only the public
facades of `geomemory` and `geoagent`, and SHALL NOT import any library
internal module.

#### Scenario: Facade-only imports
- **WHEN** the server package is inspected for imports
- **THEN** every `geomemory`/`geoagent` import resolves to a public API path

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
Long operations (ingest, index build/rebuild, benchmark, playbook runs)
SHALL return `202 {job_id}` and report progress via `GET /api/v1/jobs/{id}`
until terminal status; job results SHALL surface library outcomes including
ingest dedup (`skipped: true`).

#### Scenario: Ingest job lifecycle
- **WHEN** a file is uploaded to `POST /api/v1/ingest`
- **THEN** the response is `202` with a job id
- **AND** polling `GET /jobs/{id}` transitions queued → running → done with
  the ingest result (asset_id, segment_count, or skipped flag)

### Requirement: SSE event stream
The server SHALL stream `asset_created`, `collection_created`, and job
progress events over `GET /api/v1/events` for UI cache invalidation.

#### Scenario: Event after ingest
- **WHEN** an ingest job completes
- **THEN** an `asset_created` event is emitted on the SSE stream

### Requirement: Hybrid LLM compute, secrets server-side
The server SHALL default LLM selection to the API provider
(OpenAI-compatible), support `llamacpp` as local fallback, and read API keys
from server environment variables (name from `llm_api_key_env`, default
`GEOMEMORY_LLM_API_KEY`). Keys SHALL NOT be accepted from clients,
persisted, or returned by any endpoint. Unavailable backends SHALL produce
`503` errors or library abstention results, never stack traces. The gateway
SHALL seed `llm_api_base_url` and `llm_model_id` from the server env
(`GEOMEMORY_LLM_API_BASE_URL` / `GEOMEMORY_LLM_MODEL_ID`) when a workspace is
created or opened, so a deployment can configure the LLM connection without
editing stored settings.

#### Scenario: Key never crosses the wire
- **WHEN** any endpoint's response payload is inspected
- **THEN** the API key value does not appear

#### Scenario: Key not settable through settings
- **WHEN** `PUT /api/v1/workspace/settings` receives a body containing
  `llm_api_key_env`
- **THEN** the server responds `422` and does not store or apply a key

#### Scenario: LLM probe
- **WHEN** `GET /api/v1/doctor/llm` is called
- **THEN** it reports provider, key configured (bool), base URL, model id,
  and context window without leaking the key, and works without an open
  workspace (falling back to gateway defaults)

### Requirement: Sandboxed artifact serving
`GET /api/v1/agent/files/*` SHALL serve only files under the active
workspace's `runs/` directory, normalizing paths and rejecting traversal.

#### Scenario: Traversal rejected
- **WHEN** a request path contains `..` or escapes the runs root
- **THEN** the response is `404`

### Requirement: Uniform error envelope
All error responses SHALL use `{error: {code, message, detail?}}`.

#### Scenario: Validation failure
- **WHEN** a request body fails schema validation
- **THEN** the response is `422` with code `validation`
