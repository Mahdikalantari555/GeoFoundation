# Data Flow (summary)

Full detail with mermaid diagrams: [current-state/data-flow.md](current-state/data-flow.md).

Five flows carry all data through GeoMemory:

1. **Ingest** (`GeoMemory.ingest`): bytes → SHA-256 → duplicate-hash short-circuit → MIME/kind detect → loader+chunker parse → blob to `objects/` → `asset`/`asset_revision` rows → `segment` rows (FTS5 triggers fire) → raster/vector spatial persistence (RTree) → commit → `asset.created` event → completed `Job`.
2. **Index build** (`build_index(space_id)`): segments from SQLite → embedder (GGUF or hashing) → backend upsert (numpy/txtai/vector) → JSON manifest.
3. **Search** (`GeoMemory.search`): QueryParser → parallel sparse (FTS5) + dense (vector backend) retrieval → RRF fusion → dedup + diversity cap → spatial/temporal/sensor filters → top_n `SearchResult` (+ persisted `RetrievalRun` audit row).
4. **Ask** (`GeoMemory.ask`): search for evidence → token-budgeted context pack → mode prompt (grounded_qa/research/code) → llama.cpp generation → `[n]` citation extraction/mapping/validation → abstention check → persist conversation/turn/answer/citation → `QAResult`.
5. **Feedback loop**: feedback events → dataset example build + dedup → review queue (pending→accepted/rejected) → export as rag_eval / qa_eval / sft / preference with dataset card.

Provenance thread through everything: `answer → citation → segment(locator) → asset_revision(hash) → objects/<sha256>`.
