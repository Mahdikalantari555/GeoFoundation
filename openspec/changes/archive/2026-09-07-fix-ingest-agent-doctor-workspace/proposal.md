# Proposal: fix-ingest-agent-doctor-workspace

## Why

Three user-visible regressions block daily use and violate the platform invariant "nothing silently breaks":

- **Ingest (input data) dead** — drag-drop + file picker succeed but no job progress, dedup banner, or error surfaces. Uploads either 422 on extension, 409 workspace confusion, or 500 swallowed without UI feedback.
- **Agent chat dead** — `/api/v1/agent/chat` SSE stream not consumed or crashes silently; conversation never appears, no error card, no retry. Users cannot tell if workspace not ready (409), LLM not configured (503), or stream disconnected.
- **Doctor shows `[object Object]`** — `GET /api/v1/doctor` embeds rich dicts (`llm_provider`, `qdrant`, `pdf_parser`, `vision`) inside `checks`. Web's `CheckList` calls `String(value)` on objects → renders `[object Object]` for every row. The environment/LLM sections lose their structured data.

Additional friction:

- Default workspace root is ad-hoc; long-term home must be the gitignored `/mnt/data/Projects/RS/Thesis_Project/GeoFoundation/Workspaces` (dev) and `/workspace` (container) with auto-creation and consistent seeding of `GEOMEMORY_LLM_*` env.
- Silent failures exist elsewhere (job error never shown, SSE disconnect invisible, 5xx swallowed by `unhandled_exception_handler` with no detail, validation errors not mapped to field). Requirement: **every failure pathway renders an explicit error envelope with `code/message/detail` and a recovery action**.

## What Changes

### Ingest reliability
- Harden `POST /api/v1/ingest` + `/ingest/bytes`: normalize extension check (case-insensitive, allow `.tif/.tiff/.geojson/.gpkg/.ipynb` + text family), surface `unsupported_format` 422 with accepted list, cap file size with `413 payload_too_large`, and ensure multipart `index_after` boolean coercion.
- Job pipeline: ensure temp file lifecycle owned by job closure, emit `asset_created` on success, `job_progress error` on failure, and return `skipped:true` payload flattened for dedup banner.
- UI: `IngestPage` shows per-job state (queued→running→done/error), retry, collection not found, workspace closed guard, network error, and dedup banner; disables submit until workspace open + collection selected.

### Agent chat reliability
- Unify `POST /api/v1/agent/chat` contract: always emit `conversation` → `thinking` → (`tool_start`/`tool_end`)* → `message` (streaming + final) → `done`, and on any exception emit `error` (`code` from `GeoFrontError` or `internal_error`) before `done`. Abort via `AbortController`, timeouts → `error` not silent close.
- Init guard: `AgentService.is_initialized` checks actual workspace binding; surface `409 agent_not_ready` with actionable hint "Open a workspace" (not blank).
- Web `AgentChatPage`: streaming buffer, tool timeline, guardrail cards (`budget`, `llm_unavailable`), citation chips, conversation persistence, explicit error banners + retry; never swallows fetch/SSE exceptions.

### Doctor + workspace defaults
- Server: `GET /api/v1/doctor` returns typed shape `{ environment, workspace, workspace_open }` where `checks` only holds primitives (`bool|string|number`); rich diagnostics move to top-level `diagnostics: { llm, qdrant, pdf_parser, vision }` with explicit types. Legacy `checks.llm_provider` etc removed. `GET /api/v1/doctor/llm` returns flat typed model (no nested object leakage).
- Web: new `DoctorPage` renders environment table (core/optional deps badges), workspace checks list (boolean badges, string/number values), collapsible diagnostics sections for llm/qdrant/pdf_parser/vision, and LLM probe section with `provider/base_url/model_id/key_env/key_configured`. No `String(object)` path remains.
- Workspace defaults: `GEOFOND_WORKSPACE` default is `/mnt/data/Projects/RS/Thesis_Project/GeoFoundation/Workspaces` in dev (`server/src/geofront_api/state.py` + `workspace.py` create/open default) and `/workspace` inside containers; auto-creates parent dir; `.gitignore` normalizes `Workspaces/` + `/Workspaces/` + `**/Workspaces/`; docs + Doctor show resolved path.

### No silent breaks (cross-cutting)
- All error paths return `{error:{code,message,detail?}}` — `GeoFrontError`, validation (422 with field errors), 404/409/413/503, and 500 with `request_id` + server log correlation (no stack leak in prod, full log server-side).
- Client: generated `openapi-fetch` wrapper normalizes non-2xx to envelope; TanStack Query `onError` + global `ErrorBoundary` + SSE `error` event → toast/banner + retry. Jobs poll shows `progress/error`. Ingest/agent/search/ask/collections all have explicit `loading/empty/error` states.
- Logging: structured request log (method/path/status/ms/request_id/workspace_id) + job/agent failure logs; `X-Request-ID` header round-trip.

## Capabilities

### New Capabilities
(none — hardening existing capabilities)

### Modified Capabilities
- `gateway-server`: ingest validation/errors, agent chat SSE contract, doctor diagnostics shape, workspace default path, uniform error envelope + request-id.
- `web-app`: Ingest page job/error states, Agent chat streaming/error handling, Doctor rendering + diagnostics, workspace switcher default path, global error boundary/SSE error surfaces.

## Impact

- **Code**: `server/src/geofront_api/routers/{ingest,doctor,workspace}`, `state.py`, `errors.py`, `main.py` (request-id middleware), `services/agent.py`; `apps/web/src/features/{ingest,agent,doctor,workspace}` + `api/*` + `components/ErrorBoundary`.
- **APIs**: `GET /api/v1/doctor` response shape change (additive `diagnostics`, `checks` flattened) — web is only consumer, regenerated client. `POST /api/v1/ingest` / `POST /api/v1/agent/chat` error codes clarified.
- **Risks**: doctor shape change needs web in lockstep (same change, single PR) — mitigated by generated client and `pnpm gen:api` gate. Workspace default path must not break existing `Workspaces/test*` fixtures → migration keeps backwards compat (open still accepts any path).
