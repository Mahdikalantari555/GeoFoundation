# GeoFoundation — Project Context

Data-sovereign AI platform for remote sensing research: knowledge
(workspaces, rasters, documents, feedback) stays on the local machine, while
LLM compute is **hybrid** — remote OpenAI-compatible API **by default**
(e.g. Kilo gateway), local GGUF models as offline fallback. Monorepo
assembling libraries (memory, agent, algorithms), a gateway server, and
apps. Detailed docs: `docs/CHARTER.md`, `docs/ARCHITECTURE.md`,
`docs/STRUCTURE.md`, `docs/SPEC_SERVER.md`, `docs/SPEC_WEB.md`.

## What lives here

| Path | Role |
|---|---|
| `libs/geomemory` | memory engine (SQLite FTS5/RTree, hybrid search, citations, feedback) |
| `libs/geoagent` | agent SDK (tool registry, playbooks, LLM loop) |
| `libs/metric_et` | (future) METRIC evapotranspiration library |
| `server/` | FastAPI gateway — `/api/v1`, the only surface apps consume |
| `apps/web/` | React Vite SPA (en/fa RTL) |

## Technical context

- Python ≥3.10 in conda env `ai`; Pydantic v2 everywhere; FastAPI gateway.
- React + Vite + TypeScript strict; pnpm; shadcn/ui + Tailwind logical props.
- SQLite **single-writer** invariant: gateway runs one worker, one active
  workspace, writes serialized behind an asyncio lock.
- LLM compute is hybrid: `llm_provider` defaults to `"api"` (OpenAI-compatible
  base URL, Kilo gateway default); `"llamacpp"` serves offline. API keys live
  in **server env** (`GEOMEMORY_LLM_API_KEY` by default, name configurable via
  `llm_api_key_env`) — never persisted to the workspace DB, never sent to the
  web client.
- Apps import **only** gateway HTTP API; gateway imports **only** public
  facades (`geomemory`, `geoagent`) — never internals.
- Content identity = SHA-256; provenance chain answer→citation→segment→
  revision→objects/<sha256> must stay traceable.

## Established conventions

- `ruff` (line-length 100) + `mypy --strict` for Python; ESLint + Prettier for TS.
- Tests: pytest (`unit`/`integration` markers) in `server/tests`; Vitest +
  Testing Library in `apps/web/src/**/*.test.tsx`.
- Long ops are background jobs (`202` + job id) — UI never blocks.
- Workspaces, `.env`, models, node_modules never committed.
- openspec changes archive into `openspec/specs/` when complete.
