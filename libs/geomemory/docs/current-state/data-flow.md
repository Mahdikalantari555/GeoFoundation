# Data Flow — Current State

Status: as-is, `main` @ `364b897`.

## 1. Ingestion (synchronous path — `GeoMemory.ingest`)

`core/workspace.py:208` `Workspace.ingest(source, collection_id, *, parser=None, index_after=True) -> Job`

```mermaid
flowchart TD
    A[source: str / Path / bytes] --> B[read raw bytes]
    B --> C[sha256 content hash]
    C --> D{hash exists in\nasset_revision?}
    D -- yes --> E[return completed Job\nskipped: duplicate]
    D -- no --> F[detect MIME → kind\ndocument·code·raster·vector·table]
    F -- document/code/table --> G[parse + chunk\nloaders + chunkers]
    F -- raster/vector --> H[rs loader → chunks + spatial payload]
    G --> I[ObjectStore.put_bytes\nobjects/ab/cd/sha256]
    H --> I
    I --> J[INSERT asset + asset_revision\nimmutable revision]
    J --> K[INSERT segments\nFTS5 triggers keep segments_fts in sync]
    K -- spatial payload --> L[persist_scene / persist_vector_layer\nraster_scene · raster_tile · vector_layer + RTree]
    L --> M[UPDATE asset.current_revision_id\nCOMMIT]
    M --> N[EventBus emit asset.created]
    N --> O[return completed Job\nasset_id·revision_id·segment_count]
```

Notes:
- `parser_version="0.1.0"` is stamped on every revision.
- The async-shaped path is `services/ingestion_service.py`: `ingest()` inserts a `pending` job row and returns it; actual work still runs when `JobQueue.run(job_id, fn)` is invoked by the caller.

## 2. Index build (`IndexService.build`, exposed as `GeoMemory.build_index(space_id)`)

```mermaid
flowchart LR
    A[segments from SQLite] --> B[choose embedder\nllama-cpp GGUF or hashing fallback]
    B --> C[embed batched vectors]
    C --> D[backend upsert\nnumpy / txtai / vector backend]
    D --> E[IndexManifest written to index dir]
```

- Space ids isolate modality: text spaces vs vision spaces; never mixed.
- `rebuild_index()` drops and reconstructs from DB via `RetrievalBackend.rebuild(manifest)`.
- Image side: `ImageIndex` stores vision embedding vectors keyed by target id; persisted with its own manifest under `<index_dir>/image`.

## 3. Search (`GeoMemory.search` → retrieval stack)

```mermaid
flowchart TD
    Q[query + optional SpatialFilter/TemporalFilter/sensor/collections] --> P[QueryParser\nclean · extract filters · detect intent]
    P --> S1[sparse: SQLite FTS5\nsegments_fts MATCH]
    P --> S2[dense: vector backend\ncosine / txtai]
    S1 --> F[fusion\nmode=hybrid → rrf_fuse\ndense/sparse → passthrough\nelse linear_fuse]
    S2 --> F
    F --> G[deduplicate + diversity cap\nmax_per_document = 3]
    G --> H[apply_spatial_filter → apply_temporal_filter → sensor filter]
    H --> T[top_n hits → SearchResult]
    T --> R[persist RetrievalRun\nquery_plan · filters · latency_ms]
```

- Workspace keeps an internal `_WorkspaceSearchAdapter(SearchService)` so collection-scoped searches reuse the same orchestration (`core/workspace.py:964`).
- Hit metadata carries locator, sensor, spatial payload used by filters and citations.

## 4. Ask / grounded QA (`GeoMemory.ask`)

```mermaid
flowchart TD
    Q[question] --> S[retrieve context via search stack]
    S --> CP[context_packer\ntoken-budgeted evidence block]
    CP --> PR[build_prompt mode:\ngrounded_qa / research / code]
    PR --> LLM[LLMBackend.generate\nllama.cpp GGUF · NullBackend abstains]
    LLM --> CI[citation.extract_citation_keys\nmap_citations → validate_citations]
    LLM --> AB[should_abstain? → AbstentionError / flagged result]
    CI --> PS[persist Conversation · Turn · Answer · Citation\n+ prompt_hash + model id]
    PS --> OUT[QAResult: text · citations · abstained]
```

## 5. Feedback → dataset export loop

```mermaid
flowchart LR
    U[user feedback event] --> FE[feedback builders\nrating · source relevance · edited answer · preferred sources]
    FE --> DE[build_dataset_example\ndedup via duplicate grouping]
    DE --> RQ[ReviewQueue\npending → accepted/rejected]
    RQ -- accept --> EX[exporters by task_type\nrag_eval · qa_eval · sft · preference]
    EX --> DC[dataset_card.jsonl + card metadata]
    RQ -- reject --> X[dropped, reviewer recorded]
```

## 6. Evaluation (`eval/`)

`BenchmarkRunner.run(benchmark_path, config)` loads JSONL benchmark items → for each item runs retrieval (`search`) and/or QA (`ask`) → aggregates recall@k/precision@k/mrr@k/ndcg@k and QA metrics → reporter emits JSON or Markdown. Driven by CLI `geomemory eval run` and `scripts/run_phase1_benchmark.py`.

## 7. Cross-cutting flows

- **Provenance chain**: `asset → asset_revision(hash) → segment(locator) → citation(answer)` — every answer traceable to source bytes in `objects/`.
- **Events**: only `asset.created` is emitted today; bus has no internal subscribers (fire-and-forget extension point).
- **Jobs**: `job` table rows record state/progress/checkpoint; used by ingestion service and CLI feedback loops; execution is synchronous.
