# Tasks — GeoFoundation gateway + web app

Legend: [ ] pending · [x] done · each task ends with commit + verify.

## M0 — Scaffold

- [x] Task: server skeleton (app factory, CORS, /health, error envelope, 409 workspace guard)
  - Acceptance: `GET /health` returns `{status, workspace: closed, llm}`; unknown route returns envelope
  - Verify: `conda run -n ai pytest server/tests -q`
  - Files: server/src/geofront_api/{main.py,state.py,schemas.py}, server/tests/test_health.py
- [x] Task: web scaffold (Vite+React+TS strict, Tailwind+shadcn init, router, app shell sidebar+header, i18n en/fa skeleton, health pill)
  - Acceptance: app boots, en↔fa flips dir, health pill polls gateway
  - Verify: `pnpm build && pnpm test`
  - Files: apps/web/**
- [x] Task: generated API client + SSE helper
  - Acceptance: `pnpm gen:api` produces typed client from running gateway
  - Verify: build passes with client import
  - Files: apps/web/src/api/**

## M1 — Workspace

- [x] Task: workspace routes (create/open/close, settings GET/PUT, stats)
  - Acceptance: lifecycle round-trip via httpx; 409s covered
  - Verify: pytest server/tests/test_workspace.py
  - Files: server/routers/workspace.py, tests
- [x] Task: Overview + Settings pages
  - Acceptance: stats cards render; settings form persists
  - Verify: pnpm build + manual smoke (en/fa)
  - Files: apps/web/src/features/{overview,settings}/**

## M2 — Knowledge base

- [x] Task: jobs registry + collections routes
  - Acceptance: 202/poll lifecycle unit-tested
  - Files: server/{jobs.py,routers/collections.py}, tests
- [x] Task: ingest routes (multipart + bytes, threadpool, dedup result)
  - Files: server/routers/ingest.py, tests
- [x] Task: assets routes (list, inspect)
  - Files: server/routers/assets.py, tests
- [x] Task: Collections + Ingest + Assets pages
  - Files: apps/web/src/features/{collections,ingest,assets}/**

## M3 — Retrieval

- [x] Task: search + ask routes (all filters; abstention passthrough)
  - Files: server/routers/{search,ask,feedback}.py, filters.py; tests (20 + 7 events)
  - Note: POST /feedback added early — Search page hit thumbs need it in M3
- [x] Task: SSE /events stream
  - Files: server/events.py (EventBus), routers/events.py; jobs/ingest/collections/workspace publish
  - Note: starlette TestClient + httpx.ASGITransport await app completion → tests use a manual ASGI harness
- [x] Task: Search page (modes, filter panel, bbox draw, score breakdown, hit feedback)
  - Files: apps/web/src/features/search/** (BBoxPicker = dependency-free SVG graticule draw)
- [x] Task: Ask page (chat UI, citations drawer, abstention card)
  - Files: apps/web/src/features/ask/**
- [x] Task: SSE cache invalidation on web (useEvents hook in AppShell)

## M4 — Ops

- [ ] Task: index/feedback/eval/doctor routes (+ /doctor/llm probe, export download)
  - Files: server/routers/{index,feedback,eval,doctor}.py, tests
- [ ] Task: Index + Review + Eval + Doctor pages
  - Files: apps/web/src/features/{index,feedback,eval,doctor}/**

## M5 — Agent

- [ ] Task: geoagent end-to-end spike (python script: chat turn + one tool call)
  - Acceptance: go/no-go + scope note recorded here
  - Files: scripts/spike_geoagent.py
- [ ] Task: agent routes (chat SSE, conversations, tools, playbooks, files sandbox, farms)
  - Files: server/routers/agent/**, tests
- [ ] Task: Agent Chat + Conversations + Tools + Playbooks pages
  - Files: apps/web/src/features/agent/**

## M6 — Geo

- [ ] Task: maps/farms artifact endpoints (if not in M5)
- [ ] Task: Maps viewer + Farms pages
  - Files: apps/web/src/features/{maps,farms}/**

## M7 — Polish

- [ ] Task: RTL audit both directions, a11y pass, empty/loading/error everywhere
- [ ] Task: Playwright smoke (open ws → ingest → search → ask abstention path)
- [ ] Task: docker-compose (gateway + web), README quickstart verified

## Cross-cutting (every milestone)

- Verify: `ruff check server && conda run -n ai mypy --strict server/src` (per repo conventions)
- Verify: `pnpm lint && pnpm build && pnpm test`
- Update this file + archive openspec change sections as they complete
