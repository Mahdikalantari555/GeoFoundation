# GeoFoundation — Architecture

## Monorepo layout

```
GeoFoundation/
├── README.md · .gitignore
├── docs/                       ← this documentation set
│   ├── CHARTER.md              vision, layers, values, roadmap
│   ├── ARCHITECTURE.md         ← you are here
│   ├── STRUCTURE.md            repo conventions, case-study pattern
│   ├── SPEC_SERVER.md          gateway HTTP API v1 spec
│   └── SPEC_WEB.md             web app spec + milestones
├── libs/                       ← versioned libraries (the platform)
│   ├── geomemory/              memory engine (git history preserved via subtree)
│   │   ├── src/geomemory/      public facade — the API contract
│   │   ├── tests/ · apps/ · docs/ · openspec/ · benchmarks/
│   │   └── geomemorytest/      external black-box suite (tests the facade only)
│   ├── geoagent/               agent SDK: tool registry, playbooks, LLM loop
│   └── metric_et/              (later) METRIC ET energy-balance library
├── server/                     ← FastAPI gateway (geofoundation/server)
│   └── src/geofront_api/
├── apps/
│   └── web/                    ← React Vite SPA (the frontend)
└── studies/                    (later) per-experiment repos-as-folders
```

Outside the monorepo (siblings, not tracked): `Ideas/` (thesis writing),
`research/`, legacy copies of GeoMemory/GeoAgent/geomemorytest until deleted.

## Gateway: the platform's face

```
Browser ── React SPA (:5173 dev / static in prod)
   │ REST (JSON) · SSE streams · multipart uploads
   ▼
FastAPI gateway (:8000, ONE worker)
   ├── imports ONLY public facades: geomemory.GeoMemory, geoagent SDK
   ├── serves workspace artifacts sandboxed (GET /files/*)
   ├── background job registry for long ops (ingest, index, benchmarks)
   └── SSE: chat tokens, job progress, domain events
```

Why one worker: SQLite has a **single writer** (WAL allows concurrent
readers). The gateway holds one active workspace and serializes writes
behind an asyncio lock. This is a platform invariant, not an
implementation detail.

## Inherited invariants (from geomemory — do not break)

1. Embedding spaces isolated per modality (text.* vs vision ids).
2. Content identity = SHA-256 of raw bytes; revisions immutable; duplicate
   ingest short-circuits.
3. Provenance chain: answer → citation → segment(locator) →
   asset_revision(hash) → objects/<sha256>.
4. Facade-only consumption: gateway/apps import `geomemory` public API,
   never internals. `libs/geomemory/geomemorytest/` enforces this
   black-box style for the whole monorepo.
5. Protocol-based extensibility (`TextEmbedder`, `VisionEmbedder`,
   `RetrievalBackend`, `LLMBackend`, geoagent tool registry).
6. Single SQLite writer; heavy/network deps behind lazy imports.

## Data flow (the platform's signature loop)

```
        ingest                search / ask              use
files ───────────▶ assets ───────────────▶ hits ──────────────▶ citations
                    │                          │
                    │                    feedback event
                    ▼                          ▼
              segments ────────▶ review queue ──▶ export JSONL
              (embedded)              (accept/reject)      │
                    ▲                                        ▼
                    └────────── (future GeoLearn) training data
                                 models/labels flow back
```

Domain events (`asset_created`, `collection_created`, job progress) are
broadcast over SSE and drive UI cache invalidation — no polling staleness.

## Deployment topology

- **Dev**: `pnpm dev` (Vite :5173, proxy → :8000) + `uvicorn` (:8000).
- **Prod (single box)**: `docker compose up` — one gateway container
  (workspace dir as mounted volume, exactly one writer container), web
  served as static files by the gateway or a sidecar nginx.
- Never run two writer processes against one workspace (gateway container
  AND geomemory CLI image simultaneously).

## Technology decisions

| Concern | Choice | Why |
|---|---|---|
| Gateway | FastAPI + uvicorn, single worker | SSE support, Pydantic-native (libs are Pydantic v2) |
| Web | Vite + React + TS strict | speed, typed OpenAPI client generation |
| Server state | FastAPI BackgroundTasks + in-proc job registry | no broker needed for single-user local platform |
| Client state | TanStack Query + Zustand | SSE-driven invalidation; small UI store |
| UI | shadcn/ui + Tailwind (logical props) | RTL-safe (fa/en), composable |
| Maps | react-leaflet | bbox draw, GeoJSON layers, OSM tiles |
| i18n | i18next, en/fa | thesis requires Persian demo |
