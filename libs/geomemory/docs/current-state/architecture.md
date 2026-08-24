# System Architecture — Current State

Status: as-is description of `main` @ `364b897`, v0.1.0 alpha.

## 1. Runtime topology

GeoMemory is an **in-process Python library**. There is no server, no daemon, no network service. Every consumer (CLI, Streamlit app, notebook) imports the library and owns a `GeoMemory` facade instance bound to a workspace directory.

```
┌─────────────────────────────────────────────────────────────┐
│  Consumers                                                  │
│  CLI (geomemory)   Streamlit dashboard   Notebooks / API    │
│  cli/main.py       apps/dashboard/*      import geomemory   │
└──────────────┬──────────────┬──────────────────┬────────────┘
               │  public API only (geomemory.GeoMemory)      │
┌──────────────▼──────────────▼──────────────────▼────────────┐
│  Facade: GeoMemory (core/workspace.py, ~1150 LOC)           │
│  open/create · collections · ingest · search · ask          │
│  build_index · feedback · review · export · benchmark       │
├─────────────────────────────────────────────────────────────┤
│  Domain modules                                             │
│  ingest/      loaders + chunkers + pipeline + job queue     │
│  embeddings/  text & vision embedders (llama.cpp / hashing) │
│  index/       numpy / txtai / vector backends + manifest    │
│  retrieval/   query parser · fusion(RRF) · filters · packer │
│  qa/          chat service · prompts · citations · abstain  │
│  rs/          raster reader/tiler/spectral · vector reader  │
│  services/    thin orchestration wrappers + doctor          │
│  eval/        metrics · benchmark runner · reporter         │
│  feedback/    events · dedup · review queue · exporters     │
├─────────────────────────────────────────────────────────────┤
│  Storage                                                    │
│  storage/database.py    SQLite (WAL, FK on)                 │
│  storage/migrations.py  version-tracked schema migrations   │
│  storage/repositories/* asset·segment·embedding·spatial·    │
│                         conversation·feedback repos         │
│  storage/object_store.py content-addressed blob store       │
└───────────────┬─────────────────────────┬───────────────────┘
                │                         │
        workspace/geomemory.db     workspace/objects/
        (SQLite WAL + FTS5+RTree)  ab/cd/<sha256>  (blobs)
```

External model assets (GGUF embedding + LLM files) are loaded lazily from paths recorded in workspace settings — never hardcoded.

## 2. Architectural style

| Pattern | Where | Notes |
|---|---|---|
| **Facade** | `core/workspace.py` → class `Workspace`, subclass `GeoMemory` | Single entry point; all consumers go through it |
| **Protocol-based backends** | `embeddings/text_embedder.py` (`TextEmbedder`), `embeddings/vision_embedder.py` (`VisionEmbedder`), `index/backend.py` (`RetrievalBackend`), `qa/backend.py` (`LLMBackend`) | Swap implementations without touching callers |
| **Registry (plugin points)** | `core/plugin_registry.py`: generic `Registry[T]`; specializations `LoaderRegistry`, `ChunkerRegistry`, `EmbedderRegistry`, `BackendRegistry` | Loaders/chunkers registered in `ingest/loaders/__init__.py` and `ingest/chunkers/__init__.py` |
| **Repository** | `storage/repositories/` | Typed row↔model mapping over raw SQL |
| **Event bus (in-process)** | `core/events.py` `EventBus` / `DomainEvent` | Workspace emits `asset.created`; no internal subscribers today |
| **Job queue (DB-backed)** | `ingest/job_queue.py` + `job` table | States: pending→running→completed/failed/cancelled; synchronous execution by default |

## 3. Layer rules (as implemented)

- Consumers must use the public API exported from `geomemory/__init__.py` (facade + Pydantic models + exceptions). The dashboard enforces this; it never imports internals.
- Heavy optional deps (rasterio, txtai, llama-cpp, pymupdf) are imported **inside functions**, not at module top level, so the base install stays light.
- Embedding spaces are isolated per modality: text space ids (e.g. `text.nomic.v1`) vs. vision space ids; vectors from different spaces are never mixed.
- All domain objects are Pydantic v2 models deriving from `GeoMemoryModel` (strict types, JSON-safe dumps).
- Content identity = SHA-256 of raw bytes; a revision is immutable; duplicate ingest short-circuits on hash match.

## 4. Key design decisions (see ADRs)

- SQLite (+FTS5, RTree) instead of a client/server DB → ADR-003
- txtai/numpy vector search instead of a dedicated vector DB → ADR-001
- GGUF via llama-cpp-python for embeddings *and* generation → ADR-002
- Hybrid retrieval fused with RRF → ADR-005
- Local-first, offline-by-default, no telemetry → ADR-006
- Content-addressed provenance chain asset→revision→segment→citation → ADR-007

## 5. Concurrency model

Single-process assumption. SQLite runs in WAL mode which allows concurrent readers with one writer; `Workspace` holds one connection per instance. Background execution exists only as `IngestionService.submit_job()` creating `pending` rows — there is no worker process; `JobQueue.run()` executes synchronously in the caller's thread.

## 6. What is NOT in the architecture yet

- No HTTP/API server layer (no REST/MCP surface).
- No multi-user or auth concept anywhere.
- No remote/cloud storage backend for blobs.
- No distributed or GPU scheduling story beyond local llama.cpp.
