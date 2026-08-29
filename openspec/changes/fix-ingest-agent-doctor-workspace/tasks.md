## 1. Server — error & workspace defaults

- [ ] 1.1 Add `X-Request-ID` middleware + envelope `detail.request_id` on 500; ensure validation handler returns field errors
- [ ] 1.2 Define `DEFAULT_WORKSPACE_ROOT` (`GEOFOND_WORKSPACE` env, dev default `/mnt/data/Projects/RS/Thesis_Project/GeoFoundation/Workspaces`, container `/workspace`), auto-`mkdir -p` on create, update `.gitignore` to canonical `Workspaces/`
- [ ] 1.3 Update `workspace.py` create/open to resolve empty path → default, seed `llm_api_base_url/model_id` from env, and report resolved path in Doctor

## 2. Server — doctor shape v2

- [ ] 2.1 Refactor `services/doctor.py` + `routers/doctor.py`: keep `checks` flat (bool|string|number|null), promote `llm/qdrant/pdf_parser/vision` to `diagnostics`; make `GET /doctor/llm` flat typed model; add tests
- [ ] 2.2 `GET /doctor` add `diagnostics` + `resolved_workspace_root`, keep backwards compat for expected boolean keys

## 3. Server — ingest hardening

- [ ] 3.1 Harden `routers/ingest.py`: case-insensitive extension, `MAX_INGEST_BYTES` 500MB 413, structured 422 `unsupported_format` with `accepted`, job error propagation to `jobs` + SSE `job_progress`
- [ ] 3.2 Add server tests for ingest 413/422/409, job error terminal, doctor shape flatness

## 4. Server — agent chat hardening

- [ ] 4.1 Fix `routers/agent/chat.py`: typed SSE contract `conversation|thinking|tool_start|tool_end|message|error|done`, `error` before `done` on any exception, AbortController support, 409 guard with hint
- [ ] 4.2 Fix `services/agent.py`: workspace-bound init (`workspace_path/geoagent`), lazy re-init on workspace switch, thread-safe streaming via `call_soon_threadsafe`

## 5. Web — API client + global error surfacing

- [ ] 5.1 Wrap generated client (`apps/web/src/api/*`) to normalize non-2xx → `ApiError{code,message,detail,status,requestId}`; TanStack `QueryCache.onError` → toast; add `ErrorBoundary`
- [ ] 5.2 Add `useEvents` SSE reconnect/error banner; job poll surfaces `status:error` with banner+retry

## 6. Web — ingest + workspace UI

- [ ] 6.1 Rebuild `IngestPage`: drag-drop+picker, collection guard, job timeline (queued→running→done/error), dedup banner (`skipped:true`), 422/413 banner with accepted list
- [ ] 6.2 Workspace switcher default `Workspaces` pill, Overview empty state "No workspace open", Settings reports resolved path

## 7. Web — doctor + agent chat UI

- [ ] 7.1 Rewrite `DoctorPage.tsx`: flat `CheckList`, collapsible `diagnostics` sections (llm/qdrant/pdf_parser/vision), LLM probe section, no `String(object)` path
- [ ] 7.2 Harden `AgentChatPage.tsx`: streaming buffer, tool timeline badges, citation chips, guardrail/abstention cards, error banner with retry/abort, conversation persistence

## 8. Verification

- [ ] 8.1 `conda run -n geospatial pytest server/tests -q` + `ruff check server && mypy --strict server/src`
- [ ] 8.2 `pnpm gen:api && pnpm lint && pnpm build && pnpm test` + Playwright `e2e/doctor.spec.ts` asserts no `[object Object]`, `e2e/ingest.spec.ts` + `e2e/chat.spec.ts`
