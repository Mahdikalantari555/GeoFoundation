# Implementation Plan — gateway + web app

Source specs: `openspec/changes/add-gateway-server`, `add-web-app`;
docs: `docs/SPEC_SERVER.md`, `docs/SPEC_WEB.md`. Milestones M0–M7 from
SPEC_WEB. Each milestone is a vertical slice, demoable, ends with a commit
and a `tasks/todo.md` update.

## Component map & build order

```
M0  scaffold    server skeleton ── web scaffold ── generated client
M1  workspace   server workspace routes ── web Overview+Settings      (needs: state.py, error envelope)
M2  knowledge   collections+ingest+assets routes ── pages              (needs: jobs.py, multipart)
M3  retrieval   search+ask routes ── Search+Ask pages                  (needs: SSE /events for invalidation)
M4  ops         index+feedback+eval+doctor routes ── pages             (needs: file download, LLM probe)
M5  agent       SPIKE geoagent e2e ── agent routes ── 4 pages          (needs: /agent/files sandbox)
M6  geo         farms/maps artifact endpoints ── 2 pages               (needs: leaflet layers, recharts)
M7  polish      RTL audit, a11y, Playwright smoke, docker-compose
```

Server always lands before its web milestone consumes it (contract-first:
routes + OpenAPI → regenerate client → build pages).

## Verification checkpoints

- After each server milestone: `pytest server/tests` (httpx client against
  app, tmp workspaces, no LLM key needed — abstention paths asserted).
- After each web milestone: `pnpm build` + `pnpm test` + manual smoke
  (en + fa) against a running gateway.
- M5 gate: geoagent spike result decides scope (full / reduced agent UI).

## Risks

| Risk | Mitigation |
|---|---|
| geoagent maturity | M5 spike first; reduce scope to chat+tools if playbooks/farms unready |
| SSE via Vite proxy | verify in M0 with a test event stream |
| Sync lib calls blocking event loop | run blocking facade calls in threadpool (`anyio.to_thread`), write lock serializes |
| fa translations | draft with glossary; user reviews before M4 |

## Parallelism

Within a milestone: server routes ∥ web page scaffolds; wiring sequential.
M4 (server) can proceed while M3 (web) polishes.
