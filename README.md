# GeoFoundation

Local-first, offline-by-default AI platform for remote sensing research.
Monorepo assembling the GeoMemory knowledge engine, the GeoAgent SDK, the
gateway server, and the web app built on top.

## Layout

```
libs/
  geomemory/     memory engine (SQLite+FTS5+RTree, hybrid search, citations, feedback)
  geoagent/      agent SDK (tool registry, playbooks, LLM loop)
  metric_et/     (later) METRIC evapotranspiration library
server/          FastAPI gateway — /api/v1, the only surface apps consume
apps/web/        React Vite SPA (en/fa RTL)
docs/            CHARTER · ARCHITECTURE · STRUCTURE · SPEC_SERVER · SPEC_WEB
```

## Quickstart (dev)

```bash
# python libs (conda env `geospatial`)
conda run -n geospatial pip install -e libs/geomemory -e libs/geoagent -e server

# gateway
conda run -n geospatial uvicorn geofront_api.main:app --port 8000

# web
cd apps/web && pnpm install && pnpm dev   # :5173, proxies /api → :8000
```

## Docker (single-box demo)

```bash
# gateway (8000) + web (5173 → nginx proxy to gateway)
# workspace is a named volume; mount a host dir with -v /host/ws:/workspace if needed
GEOMEMORY_LLM_API_KEY=sk-... docker compose up --build -d
curl http://localhost:8000/health
open http://localhost:5173

# logs
docker compose logs -f gateway web

# stop
docker compose down
```

`docker compose config` validates the stack; the web image is a multi-stage
Vite → nginx build, the gateway is `python:3.12-slim` with a single uvicorn
worker (SQLite single-writer invariant, AGENTS.md § Invariants).

## Docs

Start with `docs/CHARTER.md` (vision + roadmap), then
`docs/ARCHITECTURE.md`, `docs/STRUCTURE.md`, and the specs
(`SPEC_SERVER.md`, `SPEC_WEB.md`).

## Status

Scaffolding — MSc thesis phase. See `docs/CHARTER.md` § Roadmap.
