# Architecture (summary)

Full detail: [current-state/architecture.md](current-state/architecture.md).

GeoMemory is a **local-first, in-process Python library** — no server component. Layering:

1. **Consumers**: `geomemory` CLI · Streamlit dashboard (`apps/dashboard/`) · notebooks importing the public API.
2. **Facade**: `GeoMemory` (`src/geomemory/core/workspace.py`) — the single entry point; all operations (ingest/search/ask/index/feedback/eval) hang off it.
3. **Domain modules**: `ingest/`, `embeddings/`, `index/`, `retrieval/`, `qa/`, `rs/`, `services/`, `eval/`, `feedback/` — wired together via protocols (`TextEmbedder`, `VisionEmbedder`, `RetrievalBackend`, `LLMBackend`) and registries.
4. **Storage**: SQLite (WAL + FTS5 + RTree) via typed repositories, plus a content-addressed blob store (`objects/<sha256>`), plus file-based vector indexes with JSON manifests.

Core invariants: SHA-256 content identity, immutable revisions, isolated embedding spaces per modality, offline-by-default, Pydantic v2 domain models everywhere.

Key ADRs: [vector search](adr/ADR-0001-vector-search-selection.md) · [embeddings](adr/ADR-0002-embedding-model-strategy.md) · [storage](adr/ADR-0003-storage-architecture.md) · [API design](adr/ADR-0004-public-api-design.md) · [hybrid retrieval](adr/ADR-0005-hybrid-retrieval-fusion.md) · [local-first](adr/ADR-0006-local-first-offline.md) · [grounded QA](adr/ADR-0007-grounded-qa-provenance.md).
