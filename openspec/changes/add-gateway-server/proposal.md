# Proposal: add-gateway-server

## Why

GeoFoundation apps must never import library internals. The platform needs
one HTTP face that composes `libs/geomemory` and `libs/geoagent` behind a
versioned, typed API — the same seam that makes apps replaceable (web, CLI,
future MCP server) and enforces the SQLite single-writer invariant centrally.

## What Changes

- New `server/` package (`geofront_api`, FastAPI, single worker) exposing
  `/api/v1` per `docs/SPEC_SERVER.md`: workspace lifecycle, collections,
  ingest (multipart + bytes, background jobs, dedup surface), search + ask
  (all filters), assets/inspect, index build/rebuild, feedback/review/export,
  eval benchmarks, doctor (incl. LLM probe), SSE events, and the full agent
  surface (chat SSE, conversations, tools, playbooks, sandboxed files, farms).
- Server-side workspace singleton + asyncio write lock; one active workspace.
- Uniform error envelope `{error: {code, message, detail?}}`; `503` for
  unavailable LLM/embedder backends (drives abstention UI states).
- Background job registry (`202` + `GET /jobs/{id}`) for long operations.
- LLM: API provider is the default (`llm_provider: api`); key stays in
  server env; never accepted from or returned to clients.
- OpenAPI schema is the contract: the web client is generated from it.

## Capabilities

### New Capabilities
- `gateway-server`: HTTP facade over public library facades; workspace state
  machine; job registry; SSE events; sandboxed artifact serving; error model.

### Modified Capabilities
(none)

## Impact

- **Code**: new `server/src/geofront_api/` (routers/, state.py, jobs.py,
  schemas.py, main.py) + `server/tests/`. No changes to `libs/*`.
- **APIs**: additive only — new HTTP surface; library facades untouched.
- **Risks**: geoagent maturity unknown → M5 starts with an end-to-end spike;
  sync ingestion needs job wrapping (no async worker in libs).
