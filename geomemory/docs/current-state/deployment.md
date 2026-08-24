# Deployment Architecture — Current State

## Model

**Local-first, single-machine, single-process.** GeoMemory ships as a Python library + CLI + Streamlit reference app. There is no server, container, or managed deployment target today.

```
┌────────────────────────── one machine ──────────────────────────┐
│                                                                 │
│  conda env "ai" (Python ≥3.10)                                  │
│  ├─ pip install -e ".[dev,ai,docs,rs,ui]"                       │
│  ├─ GGUF models on local disk:                                  │
│  │    text embedding   nomic-embed-text-v2-moe (llama.cpp)      │
│  │    vision embedding olmoearth-nano          (experimental)   │
│  │    generation       minicpm                 (llama.cpp)      │
│  └─ processes:                                                  │
│       geomemory <cmd>        (short-lived CLI process)          │
│       streamlit run apps/dashboard/app.py   (single-user UI)    │
│                                                                 │
│  workspace/ directory = the entire deployment state             │
│    workspace.yaml · geomemory.db (+WAL) · objects/ · indexes/   │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration surface

- `workspace.yaml` (via `WorkspaceSettings`): model paths, offline flag, language (`en`/`fa`), workspace name.
- `GEOMEMORY_DASHBOARD_ROOT`: dashboard default workspace path.
- No env-based secrets; nothing phones home (offline by default).

## Data durability & backup story (as-is)

- All state is plain files → backup = copy the workspace dir.
- SQLite WAL mode gives crash-safe commits; `doctor` runs `integrity_check`.
- Blobs are content-addressed and immutable → safe to rsync/dedupe.
- **No automated backup, retention, or migration tooling exists yet.**

## Scale envelope (current)

| Dimension | Envelope | Constraint |
|---|---|---|
| Corpus size | ~10³–10⁴ segments comfortable | numpy dense search is brute-force; FTS5 fine beyond that |
| Concurrency | 1 writer, N readers (WAL) | single user assumption |
| Assets per collection | unbounded logically | listing APIs paginate poorly at large N |
| Model footprint | few GB GGUF | loaded lazily per process; no model server/shared cache |

## Operational entry points

- `geomemory doctor [-w PATH]` — dependency presence + DB integrity + settings sanity (`services/doctor.py`).
- `pytest tests/` — unit/integration/golden/e2e suites; markers gate selection.
- `scripts/run_phase1_benchmark.py`, `geomemory eval run` — performance/quality regression checks.

## Explicit non-goals in current architecture

- Multi-tenant hosting, auth, TLS — absent by design (local research tool).
- Horizontal scaling / distributed ingestion — not addressed.
- GPU orchestration — llama.cpp CPU/Metal defaults only.

## Candidate future deployment shapes (not implemented)

1. Library remains canonical; add optional FastAPI/MCP wrapper for agent access.
2. Background worker consuming the existing `job` table for async ingestion.
3. Optional S3/local-dir blob backend behind `ObjectStore` interface.
