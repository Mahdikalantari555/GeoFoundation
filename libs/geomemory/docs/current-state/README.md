# GeoMemory — Current State Documentation

Generated: 2026-08-22 · Source snapshot: `main` @ `364b897` · Version `0.1.0` (alpha)

These documents describe **what exists today**. They are descriptive, not normative. Requirements live in `.agent/spec/`; change proposals live in `openspec/changes/`.

| Document | Contents |
|---|---|
| [architecture.md](architecture.md) | System architecture, layers, runtime topology |
| [components.md](components.md) | Component map: modules, responsibilities, key classes |
| [data-flow.md](data-flow.md) | Ingestion, indexing, search, QA, feedback flows |
| [database-schema.md](database-schema.md) | SQLite schema, virtual tables, object-store layout |
| [api-inventory.md](api-inventory.md) | Public Python API + full CLI command inventory |
| [dependency-graph.md](dependency-graph.md) | Internal module dependencies + external packages |
| [deployment.md](deployment.md) | Runtime/deployment architecture (local-first) |
| [tech-debt.md](tech-debt.md) | Dead code, duplicates, missing tests/docs |

## One-page summary

GeoMemory is a local-first Python library (no server component) that turns heterogeneous research assets — documents, code, GeoTIFF scenes, GeoJSON layers — into a searchable spatiotemporal memory.

- **Facade**: everything goes through `geomemory.GeoMemory` (`src/geomemory/core/workspace.py`).
- **Storage**: one SQLite DB (`WAL`, FTS5 sparse index, RTree spatial index) + a content-addressed object store (`SHA-256`, immutable revisions).
- **Retrieval**: hybrid sparse+dense fused by RRF, then dedup/diversity/spatial/temporal/sensor filters.
- **QA**: grounded generation via llama.cpp GGUF models with citation validation and abstention.
- **Feedback loop**: raw events → review queue → versioned dataset exports (rag_eval / qa_eval / sft / preference).
- **UIs**: two Streamlit reference apps (`apps/dashboard/` is current, `apps/app.py` legacy) consuming only the public API.
- **CLI**: `geomemory` entry point with 10 commands.

Scale today: ~150 Python files, ~880 LOC-heavy modules across 12 library packages, 30 test files (unit/integration/golden/e2e), coverage gate 80%.
