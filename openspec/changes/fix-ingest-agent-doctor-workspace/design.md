## Context

Current ingest: `server/routers/ingest.py` returns 422 for unsupported suffix, but UI never shows `detail.accepted` list, and job errors are stored in `job.result.error` not surfaced. Agent chat `routers/agent/chat.py` yields SSE but swallows exceptions inside `stream()` without emitting `error`; `services/agent.py` init is not workspace-bound reliably, leading to 409 drift. Doctor `services/doctor.py` nests dicts inside `checks`; web `DoctorPage.tsx:CheckList` renders `String(dict)` → `[object Object]`. Workspace path handling scattered; `.gitignore` lists multiple `workspace` globs but canonical dev root not documented. Silent break class: 500 handler strips detail, fetch wrapper does not normalize to envelope, jobs page polls but never shows `error` field.

## Goals / Non-Goals

**Goals:**
- Ingest end-to-end works with explicit progress/error/dedup and correct file-type gate.
- Agent chat streams reliably with typed events, guardrail and LLM-unavailable states, and surfacing 409/503.
- Doctor renders correct primitives, diagnostics separated, no `[object Object]`.
- Default workspace root is canonical `Workspaces` (dev) / `/workspace` (container), gitignored, auto-created.
- Zero silent failures: every 4xx/5xx/SSE disconnect/job error renders banner + recovery.

**Non-Goals:**
- New ingestion file types beyond current `ACCEPTED_EXTENSIONS` (DOCX still disabled gap).
- Second workspace or multi-worker support (single-writer invariant stays).
- Model download UI (belongs to embedding-model-management-onnx change).

## Decisions

- **Doctor shape v2**: keep `GET /doctor` but promote rich objects out of `checks`. `checks` stays `Record<string, bool|string|number|null>` (flat). New `diagnostics: { llm, qdrant, pdf_parser, vision }` each typed. Decision rationale: frontend already expects flat badges; nesting breaks rendering. Alternative — make frontend recursively render objects — rejected (server should own typing, UI should stay simple).
- **Error envelope + request_id**: add `X-Request-ID` middleware (uuid4), include in JSON `error.detail.request_id` for 500, echo header. Keeps log correlation without leaking stack. Existing `errors.py` already envelopes; just add `request_id` field and ensure `validation_exception_handler` returns `detail` as field errors array.
- **Ingest job ownership**: keep `tempfile.TemporaryDirectory` inside `_make_ingest_job` closure (current pattern is correct) but add `try/except` → `payload["error"]` + `EventBus.publish(job_progress, {status:error})` so failures propagate to SSE + poll.
- **Agent SSE contract**: formalize events `conversation|thinking|tool_start|tool_end|message|error|done`. Client `useAgentChat` hook handles `onerror` (EventSource) → banner. `AbortController` per turn. Guardrail failures emit `guardrail` via existing path but also `error` for generic failures with `code: llm_unavailable | agent_not_ready | internal_error`.
- **Workspace default**: constant `DEFAULT_WORKSPACE_ROOT = Path(os.environ.get("GEOFOND_WORKSPACE", "/mnt/data/Projects/RS/Thesis_Project/GeoFoundation/Workspaces"))`. `POST /workspace/create` when `path == ""` or omitted → use default + auto-`mkdir -p`. Docs + Doctor report `resolved_workspace_root`.
- **Global UI hardening**: add `ErrorBoundary` at router root, `fetch` wrapper `apiFetch` that throws `ApiError{ code, message, detail, status }` on `!ok`, TanStack Query `QueryCache.onError` → toast, SSE hook `useEvents` `onerror` → reconnecting banner (not silent).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Doctor shape change breaks older web cache | Version response with `diagnostics`; `checks` keeps old boolean keys (no removal of expected booleans). Web upgrade atomic. |
| Request-id in 500 leaks internals | Only id string, no stack; stack goes to server logs. |
| Ingest size cap breaks large GeoTIFF | Set generous 500MB cap server side, surface 413 with actual size. |
| Agent SSE qdrant blocking | Keep `asyncio.to_thread(core.chat)`; streaming via `loop.call_soon_threadsafe(queue)` already correct — add timeout ping. |

## Verification

- `conda run -n geospatial pytest server/tests -q` covers ingest validation (new 413, 422 accepted list), doctor shape (flat checks, diagnostics keys), workspace default path (create with empty path → default), agent chat 409/503 stubs, request-id header presence.
- `apps/web: pnpm gen:api && pnpm lint && pnpm build && pnpm test` covers Doctor no `[object Object]` (test asserts `String(value)` not called for diagnostics), Ingest page empty/loading/error/dedup, Chat SSE error+banner, workspace switcher default.
- Playwright: `e2e/ingest.spec.ts` (open ws → upload duplicate → dedup banner), `e2e/chat.spec.ts` (workspace open → chat stream → tool timeline → guardrail mock → error banner), `e2e/doctor.spec.ts` (no `[object Object]` text).
