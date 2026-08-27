# AGENTS.md — GeoFoundation

> Guidance for AI coding agents working in this repository. Authoritative
> specs: `docs/` (CHARTER, ARCHITECTURE, STRUCTURE, SPEC_SERVER, SPEC_WEB)
> and `openspec/`. Feature work goes through openspec changes.

## What this is

GeoFoundation is a **data-sovereign AI platform for remote sensing research**.
Knowledge (workspaces, documents, rasters, feedback) stays local; LLM compute
is hybrid — remote OpenAI-compatible API **by default**, local GGUF fallback.

Monorepo assembling:

| Path | Role |
|---|---|
| `libs/geomemory/` | memory engine (hybrid search, citations, feedback) — has its own AGENTS.md, follow it when working inside |
| `libs/geoagent/` | agent SDK (tool registry, playbooks, LLM loop) |
| `server/` | FastAPI gateway `geofront_api` — `/api/v1`, the ONLY surface apps consume |
| `apps/web/` | React Vite SPA (en/fa RTL), generated API client |
| `docs/`, `openspec/`, `tasks/` | specs, change proposals, plan/todo |

## Environment & commands

All Python runs in the **`geospatial` conda env**:

```bash
conda run -n geospatial pip install -e libs/geomemory -e libs/geoagent -e server

# server
conda run -n geospatial pytest server/tests -q
conda run -n geospatial ruff check server
conda run -n geospatial mypy --strict server/src   # once code exists

# web
cd apps/web && pnpm install
pnpm gen:api   # regenerate client from running gateway (needs uvicorn up)
pnpm lint && pnpm build && pnpm test

# run dev stack
conda run -n geospatial uvicorn geofront_api.main:app --port 8000
cd apps/web && pnpm dev    # :5173 proxies /api → :8000
```

Known pre-existing failure (in libs/geomemory, not ours to fix here):
`geomemorytest/test_workspace_lifecycle.py::TestAskAbstention::test_ask_no_model_abstains_when_context_exists`.

## Invariants (do not break)

1. **Apps consume only the gateway HTTP API.** `apps/web` never imports
   `geomemory`/`geoagent`; the gateway never imports library internals —
   public facades only (`geomemory`, `geoagent` top-level APIs).
2. **SQLite single writer**: server runs one uvicorn worker, holds one
   active workspace, serializes writes behind the asyncio lock in
   `server/src/geofront_api/state.py`.
3. **Secrets are server-env only.** LLM API keys are read from the env var
   named by `llm_api_key_env` (default `GEOMEMORY_LLM_API_KEY`); never
   accepted from clients, never persisted, never returned in responses.
4. **Blocking facade calls run in a threadpool** (`anyio.to_thread`) —
   never call the sync libs directly on the event loop.
5. **Content identity = SHA-256; provenance chain stays traceable**:
   answer → citation → segment → asset_revision → objects/<sha256>.
6. **Embedding spaces are isolated per modality** (text.* vs vision ids).
7. `workspace/`, `.env`, models, `node_modules/`, venvs are **never
   committed** (root .gitignore enforces).

## Conventions

- Python: ≥3.10, strict typing, Pydantic v2, ruff line-length 100, mypy
  strict. Error responses use the envelope `{error: {code, message, detail?}}`.
- Long operations are background jobs: `202 {job_id}` → `GET /api/v1/jobs/{id}`.
- Realtime: SSE at `GET /api/v1/events`; web invalidates TanStack Query
  caches from events, no polling staleness.
- Web: TS strict, ESLint + Prettier, shadcn/ui + Tailwind **logical
  properties** (`ps/pe/ms/me` — never `pl/pr`) for RTL safety; all user
  strings via i18next (`en`/`fa`). LLM-unavailable = abstention UI state,
  never a crash.
- Commits: one concern per commit; `libs/` changes never mixed with
  server/app changes. Per-lib tags: `libs/<name>/vX.Y.Z`.
- New features: `openspec change` proposal first, implement against
  `tasks/todo.md`, archive when done.

## Where things live

- Server routers: `server/src/geofront_api/routers/` (one file per domain;
  agent subpackage under `routers/agent/`).
- Web features: `apps/web/src/features/<domain>/` — page, components, hooks
  together; shared widgets in `src/components/`.
- Gateway contract: OpenAPI schema is source of truth; regenerate the web
  client after any route change (`pnpm gen:api`) and fix type errors before
  merging.

## Working rules

- Don't edit `libs/*` unless the task explicitly says so — libs have their
  own specs, tests, and release discipline. Missing capability in a lib =
  separate change proposal in that lib.
- Don't invent requirements beyond `docs/` + `openspec/` + user instruction.
- Run lint + tests before committing (Python and/or web depending on what
  changed).
- Update `tasks/todo.md` checkboxes as tasks complete.
