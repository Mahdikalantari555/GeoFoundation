# SPEC — Web App (apps/web)

> React Vite SPA consuming the gateway (`/api/v1`). Full feature coverage of
> `libs/geomemory/geomemoryfront.md` + `libs/geoagent/geoagentfront.md`.

## Stack

Vite · React · TypeScript strict · react-router v7 · TanStack Query v5 ·
Zustand · shadcn/ui + Tailwind (logical props `ps/pe/ms/me` — RTL-safe) ·
react-hook-form + zod · i18next (en/fa, `<html dir>` flip) · react-leaflet ·
Recharts · lucide-react · openapi-typescript + openapi-fetch generated client.

## App shell

Sidebar (grouped nav) · header with workspace switcher + language toggle +
connection pill (gateway up? workspace open?). All pages: loading/empty/error
states; bilingual smoke-check (en + fa/RTL).

## Pages (16)

### Workspace group
1. **Overview** — stat cards (collections, assets, segments, storage bytes,
   feedback counts), index manifest status, live recent events (SSE), open/
   create workspace dialog.
2. **Settings** — workspace config form (name, language, offline, model/
   embedding/vision paths, batch_size) → `PUT /settings`.
3. **Doctor** — environment table (core/optional deps with badges), workspace
   structural check, round-trip smoke test.

### Knowledge group (geomemory)
4. **Collections** — card grid, create dialog, archive (confirm), drill into
   assets.
5. **Ingest** — drag-drop + picker, collection select, index_after toggle,
   format badges (DOCX disabled), progress, dedup banner (`skipped: true`),
   segment-count summary.
6. **Search** — query bar, mode tabs (sparse/dense/hybrid), top_k/top_n,
   filter panel: collections multi-select, spatial (bbox draw on mini-map or
   geometry_id + op), temporal (field + date range), sensor chips; results
   with score bar + sparse/dense breakdown, snippet, locator chip, per-hit
   thumbs up/down → feedback event.
7. **Assets** — filterable table; detail drawer: revision, segments, scenes
   (bbox map, acquired_at, sensor, tiles), layers, observations.
8. **Index** — space selector, build/rebuild + progress, manifest status;
   vision space flagged experimental.
9. **Feedback/Review** — review queue cards, accept/reject + reviewer id,
   export panel (task type → JSONL download).
10. **Eval** — benchmark JSONL upload, config, run + progress, metrics table
    (precision@k, recall@k, MRR, latency) + charts.

### Agent group (geoagent)
11. **Agent Chat** — SSE streaming transcript, multi-turn, `[S#]` citation
    chips → source drawer (segment + locator), per-turn tool-run timeline
    (status, duration, args, cache-hit badge), guardrail error cards,
    "save as playbook".
12. **Conversations** — session list sidebar, load history.
13. **Tools** — live manifest catalog (built-in/plugin/playbook), JSON-schema
    → auto-generated invoke form, result render: JSON / table / map layer.
14. **Playbooks** — list, run with param form, progress timeline.

### Geo group
15. **Maps** — artifact viewer: map.png choropleths + GeoJSON overlays from
    `runs/`, layer list, opacity, legend from symbology breaks; zonal-stats
    tables.
16. **Farms** — registry table; farm card: stress report (trend table, worst
    date, sparkline from stats.csv, map thumb, [S#] sources), recommendation
    evidence pack (stress label, expert-rule hits, data gaps → abstention
    state), links to reports collection.

## State model

- Zustand: UI prefs (theme, language), workspace mirror `{status, path,
  settings}`, chat transcript store (streaming appends, AbortController).
- TanStack Query keys: `workspace`, `stats`, `collections`, `assets`,
  `asset/{id}`, `review-queue`, `tools`, `playbooks`, `conversations`,
  `conversation/{id}`, `jobs/{id}` …
- SSE `/events` → invalidation map: `asset_created` → `assets`,`stats`;
  `collection_created` → `collections`,`stats`; `job_progress` → `jobs/{id}`.
- Long jobs: poll `jobs/{id}` with backoff or subscribe via SSE.

## Layout

```
apps/web/
├── vite.config.ts             # dev proxy /api → :8000
└── src/
    ├── app/                   # router, providers, shell
    ├── api/                   # generated client + SSE helpers
    ├── features/              # one folder per page/domain
    ├── components/            # shared shadcn pieces + widgets
    ├── i18n/                  # en/ fa/ + RTL provider
    ├── lib/                   # utils, query keys, zod schemas
    └── stores/                # zustand
```

## Milestones

| # | Scope | Done when |
|---|---|---|
| M0 | Scaffold: Vite + Tailwind + shadcn + router + shell + i18n skeleton; gateway skeleton with /health + error envelope; OpenAPI→TS client gen | app boots, language flips RTL, health pill works |
| M1 | Workspace: create/open/close, settings form, stats | Overview + Settings live end-to-end |
| M2 | Knowledge: collections CRUD, ingest (upload, dedup, progress), assets + inspect | M2 pages live |
| M3 | Search + Ask: all modes/filters, bbox draw, citations, abstention | full search page + grounded chat |
| M4 | Ops: index, review queue + export, benchmark, doctor | M4 pages live |
| M5 | Agent: chat SSE, conversations, tools, playbooks (starts with a geoagent end-to-end spike) | M5 pages live |
| M6 | Geo: maps viewer, farms reports | M6 pages live |
| M7 | Polish: RTL audit, a11y, Playwright smoke, docker-compose packaging | demo-ready |
