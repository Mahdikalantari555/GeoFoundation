# Proposal: add-web-app

## Why

The platform needs a human face: full-featured, bilingual (en/fa RTL)
React app covering every feature of geomemoryfront.md and geoagentfront.md —
ingest, hybrid search, grounded chat with citations, the review/feedback
loop, agent tooling, maps, and farm reports. It consumes the gateway only.

## What Changes

- New `apps/web/` Vite + React + TS-strict SPA: 16 pages in 4 groups
  (Workspace, Knowledge, Agent, Geo) per `docs/SPEC_WEB.md`.
- Generated typed API client (OpenAPI → openapi-typescript/openapi-fetch).
- TanStack Query + SSE-driven invalidation; Zustand for UI/workspace/chat.
- shadcn/ui + Tailwind with logical properties (RTL-safe); i18next en/fa.
- react-leaflet (bbox draw, GeoJSON layers), Recharts (metrics, trends).
- LLM-unavailable states rendered as abstention, never crashes.

## Capabilities

### New Capabilities
- `web-app`: pages, state model, i18n/RTL, generated client, realtime.

### Modified Capabilities
(none)

## Impact

- **Code**: new `apps/web/` only; depends on gateway-server change.
- **Risks**: SSE through dev proxy; Persian glossary needs native review;
  geoagent pages depend on M5 spike outcome.
