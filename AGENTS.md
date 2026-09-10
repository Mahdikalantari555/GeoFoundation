# AGENTS.md — agy Agent Guidelines & WSL Development Environment(This is just for agy Agent that works from Windows)

## 1. Operating Environment & Execution Model(just use this if you are agy agent.)

* **Host System**: Windows is the **HOST ONLY**.
  * **DO NOT** create or write project code/artifacts into Windows host paths (except this configuration).
  * **All** development work, project files, package installs, and code modifications live inside WSL (Ubuntu).
* **WSL Target Distribution**: `Ubuntu`
* **WSL Base Path**: `\\wsl.localhost\Ubuntu\` (or `/home/asus/` inside WSL)

---

## 2. Package Manager Hierarchy (Strict Precedence)

1. **`bun` (Always Preferred)**:
   * Binary path: `/home/asus/.bun/bin/bun`
   * Use `bun` for running scripts, installing packages, tests, and adding skills (`bunx skills add <skill>`).
2. **`pnpm` (Secondary)**: Use when repository has existing `pnpm-lock.yaml` or explicit requirement.
3. **`npm` (Last Resort)**: Use only if neither `bun` nor `pnpm` is supported.

---

## 3. Project Locations & Conda Environment

* **Primary Project Directory**:
  * Inside WSL: `/home/asus/Projects/GeoFoundation`
  * From Windows path: `\\wsl.localhost\Ubuntu\home\asus\Projects\GeoFoundation`
* **All Projects Root**:
  * Inside WSL: `/home/asus/Projects/`
* **Python / Conda Environment**:
  * Miniforge Path: `/home/asus/miniforge3`
  * Active Environment: `geospatial` (`/home/asus/miniforge3/envs/geospatial`)
  * Python Binary: `/home/asus/miniforge3/envs/geospatial/bin/python`

---

## 4. Command Execution Standard in WSL

Always execute project commands in WSL under the `geospatial` conda environment.
Pattern for running commands:

```bash
wsl -d Ubuntu bash -c "export PATH=/home/asus/.bun/bin:\$PATH && source /home/asus/miniforge3/bin/activate geospatial && cd /home/asus/Projects/<ProjectName> && <COMMAND>"
```

---

## 5. OpenSpec Standard Workflow

**Always use OpenSpec in projects.**

* **Spec Location**: `<project-root>/openspec/`
* **Workflow**:
  1. **Proposals First**: Any new feature or architectural modification starts with an OpenSpec change proposal in `openspec/changes/`.
  2. **Track Tasks**: Break tasks down and follow `tasks/todo.md` / `openspec` tasks.
  3. **Respect Specs**: Always cross-reference `openspec/specs/` and `docs/` before implementing changes.
  4. **Archive on Completion**: Follow the spec lifecycle and archive completed changes in `openspec/changes/archive/`.

---

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
3. **Secrets handling.** LLM API keys are read from the env var named by
   `llm_api_key_env` (default `GEOMEMORY_LLM_API_KEY`). Keys **MAY** be set
   at runtime via `PUT /api/v1/workspace/settings` field `llm_api_key` → the
   gateway sets `os.environ[effective_key_env]` in-process (never persisted to
   workspace DB, never returned); `llm_api_key_env` itself may be updated.
   Keys are read from env at call time; never persisted, never returned.
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
