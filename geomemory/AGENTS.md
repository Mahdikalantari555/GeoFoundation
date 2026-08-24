# AGENTS.md — GeoMemory

> Guidance for AI coding agents working in this repository. For authoritative
> requirements, see `.agent/spec/`. For the change-workflow, see `CLAUDE.md`
> (`/opsx:propose` → `/opsx:apply` → `/opsx:archive`). For an as-is description
> of the system, see `docs/` (generated audit).

## What this is

GeoMemory is a **local-first, in-process Python library** (no server) that turns
heterogeneous research assets — documents, code, GeoTIFF scenes, GeoJSON layers —
into a searchable, spatiotemporal, citation-grounded memory.

- Version `0.1.0`, alpha, Python ≥3.10, MIT.
- Everything runs on the user's machine; offline by default; no telemetry.
- Consumers: `geomemory` CLI, Streamlit dashboard (`apps/dashboard/`), notebooks.

## Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.10+ |
| Models | Pydantic v2 (every domain object extends `GeoMemoryModel`) |
| Storage | SQLite — WAL, FTS5 (sparse), RTree (spatial), `+` content-addressed object store |
| Embeddings | llama-cpp-python (GGUF: `nomic-embed-text-v2-moe`, `olmoearth-nano`) with n-gram hashing fallback |
| Vector search | in-process backends (numpy / txtai / persisted vector backend) — **no dedicated vector DB** |
| QA | llama-cpp-python (`minicpm` default) via `LLMBackend` protocol; citation + abstention |
| CLI | Click (`geomemory` entry point, 10 commands) |
| RS (optional) | rasterio, shapely, geopandas, Pillow |
| Test/Lint | pytest, pytest-cov, ruff, mypy `--strict` |

Runtime deps are minimal (`pydantic`, `numpy`, `click`, `PyYAML`); heavy deps
(txtai, llama-cpp, rasterio, pymupdf, streamlit) are optional extras and imported
**lazily** inside functions.

## Repo layout

```
src/geomemory/
  core/        facade (GeoMemory), models, config, events, hashing, registries
  ingest/      loaders, chunkers, pipeline, DB-backed job queue
  embeddings/  text/vision embedder protocols + GGUF/hashing impls
  index/       RetrievalBackend impls (numpy/txtai/vector), ImageIndex, manifests
  retrieval/   query parser, RRF fusion, dedup/diversity, spatial/temporal/sensor filters
  qa/          ChatService, prompts, citation mapping, abstention, llama.cpp backend
  rs/          raster reader/tiler/preview/spectral; vector reader; persist
  storage/     SQLite connect/migrate, ObjectStore, repositories, schema.sql v1
  feedback/    events, dedup, review queue, dataset exporters
  eval/        retrieval/QA metrics, benchmark runner, reporter
  services/    thin orchestration wrappers + doctor
  cli/         Click command group (lazy imports)
apps/          Streamlit UIs (dashboard/ is canonical; app.py legacy)
docs/          current-state/*, adr/*, gap-analysis.md, roadmap.md  ← generated audit
openspec/      specs/ (as-is capability specs), changes/ (proposals)
.agent/spec/   authoritative requirements + design docs (do not invent beyond these)
```

## Key invariants (do not break)

1. **Embedding spaces are isolated per modality.** Never mix text and vision
   vectors in one space. Space ids carry the modality (`text.*`, vision ids).
2. **Content identity = SHA-256 of raw bytes.** Revisions are immutable.
   Duplicate ingest (same hash) must short-circuit (see `GeoMemory.ingest`).
3. **Provenance chain**: `answer → citation → segment(locator) → asset_revision(hash) → objects/<sha256>`. Keep it traceable.
4. **Public API contract** lives in `src/geomemory/__init__.py` (facade `GeoMemory`
   + Pydantic models + exceptions). The dashboard consumes **only** this surface.
   The Streamlit app must never import internals.
5. **Protocol-based extensibility**: `TextEmbedder`, `VisionEmbedder`,
   `RetrievalBackend`, `LLMBackend` are the extension seams. Add impls, don't fork callers.
6. **Single SQLite writer** (WAL). Don't introduce a second connection per request
   without considering `SQLITE_BUSY`. Heavy/network deps stay behind lazy imports.

## How to work here

Run all code/tests in the **`ai` conda environment** (per `CLAUDE.md`):

```bash
conda run -n ai python -m pytest tests/ -q
conda run -n ai ruff check src tests
conda run -n ai python -m mypy --strict src/geomemory
```

- pytest markers: `unit`, `integration`, `golden`, `e2e`, `spike`.
- `tests/` must pass; coverage gate is 80% (configured, not yet CI-enforced).
- Prefer the knowledge-graph MCP tools (`search_graph`, `get_code_snippet`,
  `trace_path`) over grep/glob for code discovery.
- Changes go through the opsx workflow: propose spec → apply → archive. Don't edit
  `.agent/spec/` without updating `.agent/CHANGELOG.md`.

## Search orchestration (post-audit)

Retrieval fusion/filtering now has a **single canonical path**:
`retrieval/fusion.rrf_fuse` + `retrieval/search_service.apply_hit_filters`
(spatial → temporal → sensor) + `hit_sensor`. `Workspace.search` reuses these —
do **not** reintroduce private copies. Remaining convergence (route facade
FTS/dense retrieval through `SearchService` as `RetrievalBackend` adapters) is a
roadmap v0.1 item, not yet done.

## Documentation map

| Need | Read |
|---|---|
| Architecture overview | `docs/current-state/architecture.md` |
| Component map | `docs/current-state/components.md` |
| Data flows | `docs/current-state/data-flow.md` |
| DB schema | `docs/current-state/database-schema.md` |
| API inventory | `docs/current-state/api-inventory.md` |
| Dependencies | `docs/current-state/dependency-graph.md` |
| Deployment | `docs/current-state/deployment.md` |
| Tech debt | `docs/current-state/tech-debt.md` |
| Decisions (ADRs) | `docs/adr/` |
| Gaps vs goals | `docs/gap-analysis.md` |
| Roadmap | `docs/roadmap.md` |

## Known gaps / watch-outs (see `docs/gap-analysis.md`)

- No DOCX loader despite `python-docx` declared in `[docs]` extra.
- Vision embedding path is experimental (placeholder still present).
- No HTTP/MCP server, no async job worker — ingestion is synchronous.
- `python-docx` declared but unused; `ai`/`rs` extras optional and lazy.
- Pre-existing `ruff`/`mypy` violations exist in untouched code; don't pile on.
- OpenDataLoader PDF (`[opendataloader]` extra) requires Java 11+ on PATH; falls back to PyMuPDF when unavailable.

<!-- OPENWIKI:START -->

## OpenWiki

This repository has a generated `openwiki/` evidence index. It is optional just-in-time context, not required startup reading.

- Treat source code and tests as authoritative. A brief's unknowns and review items are verification gaps, not automatic requirements.
- Prefer the narrowest quiet validation that proves the changed behavior. Preserve complete failure output.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
