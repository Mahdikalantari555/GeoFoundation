# GeoMemory Frontend — Feature Reference

> Complete feature inventory for a React frontend consuming the GeoMemory
> public API (`geomemory.GeoMemory`). All features map 1:1 to the Python
> facade class in `src/geomemory/core/workspace.py`.

---

## 1. Workspace Lifecycle

| Feature | API Method | Description |
|---|---|---|
| Create workspace | `GeoMemory.create(path, config)` | Initialize a new workspace at `path` with name, offline mode, language |
| Open workspace | `GeoMemory.open(path)` | Open existing workspace (validates `.geomemory` marker) |
| Close workspace | `ws.close()` | Release SQLite connection |
| Update settings | `ws.update_settings(**kwargs)` | Persist config changes (model_path, embedding_path, batch_size, etc.) |
| Get settings | `ws.settings` | Read current `WorkspaceConfig` |
| Workspace stats | `ws.stats()` | Dashboard metrics: collection/asset/segment counts, storage bytes, index manifest, feedback counts |

**Config fields**: `name`, `language` (en/fa), `offline` (bool), `model_path`, `embedding_path`, `vision_path`, `batch_size`.

---

## 2. Collection Management

| Feature | API Method | Description |
|---|---|---|
| Create collection | `ws.create_collection(name, description)` | New collection in workspace |
| List collections | `ws.list_collections()` | All non-archived collections |
| Get collection | `ws.get_collection(id)` | Fetch by ID |
| Archive collection | `ws.archive_collection(id)` | Soft-delete (sets `archived=1`) |

---

## 3. Ingestion

| Feature | API Method | Description |
|---|---|---|
| Ingest file | `ws.ingest(source, collection_id, parser?, index_after?)` | Parse + chunk + store + index |
| Ingest bytes | `ws.ingest(bytes_data, collection_id)` | Same pipeline from raw bytes |

**Supported formats**:
- Documents: PDF, DOCX, TXT, MD, CSV
- Code: Python, Jupyter notebooks
- Geospatial: GeoTIFF (raster), GeoJSON / GPKG (vector)
- Images: TIFF

**Deduplication**: SHA-256 hash check — duplicate ingest short-circuits with `skipped: true`.

**Spatial ingestion**: GeoTIFF → scene metadata (bbox, acquired_at, sensor, tiles). GeoJSON → vector layer (bbox).

---

## 4. Search & Retrieval

| Feature | API Method | Description |
|---|---|---|
| Hybrid search | `ws.search(query, mode, top_k, top_n, collections?, spatial?, temporal?, sensor?)` | FTS5 + dense vector + RRF fusion |
| Sparse search | `mode="sparse"` | SQLite FTS5 full-text only |
| Dense search | `mode="dense"` | Vector similarity only |
| Hybrid search | `mode="hybrid"` | Both + Reciprocal Rank Fusion |

**Filters**:
- `collections`: list of collection IDs
- `spatial`: `SpatialFilter` (bbox or geometry_id, ops: intersects/within/contains/distance_lte)
- `temporal`: `TemporalFilter` (field: acquired_at/observed_at/published_at/ingested_at, from/to ISO dates)
- `sensor`: list of sensor names (e.g., Sentinel-2, Landsat-8)

**Result**: `SearchHit` list with `id`, `score`, `sparse_score`, `dense_score`, `text`, `locator`, `metadata`.

---

## 5. Grounded QA / Chat

| Feature | API Method | Description |
|---|---|---|
| Ask question | `ws.ask(question, mode, collections?, filters?)` | Search → pack context → LLM generate → cite |

**Modes**:
- `grounded_qa`: Answer with citations from retrieved context
- `research`: Extended research mode
- `code`: Code-focused generation

**Abstention**: Returns `abstained: true` with reason when no context found or LLM unavailable.

**Citations**: Each answer includes `Citation` list with `locator`, `segment_id`, `claim_span`.

**LLM Backends** (auto-selected by `backend_factory`):
- `llama_cpp`: Local GGUF model
- `api`: Remote API (Kilo gateway, OpenAI-compatible)

---

## 6. Asset Inspection

| Feature | API Method | Description |
|---|---|---|
| List assets | `ws.list_assets(collection_id?)` | All assets, optionally filtered by collection |
| Inspect asset | `ws.inspect(asset_id)` | Full detail: asset, revision, segments, scenes, layers, observations |

**AssetDetail includes**:
- `asset`: id, kind, title, collection_id, metadata
- `revision`: hash, mime_type, size_bytes, parser_version
- `segments`: text, locator, segment_type, metadata
- `scenes`: raster scene metadata (bbox, acquired_at, sensor, tiles)
- `layers`: vector layer metadata (bbox)
- `observations`: linked observation records

---

## 7. Index Management

| Feature | API Method | Description |
|---|---|---|
| Build index | `ws.build_index(space_id)` | Embed all segments, persist dense index (incremental) |
| Rebuild index | `ws.rebuild_index(space_id)` | Full rebuild from SQLite source |

**Space IDs**: `text.nomic.v1` (default), `text.hash.v1` (offline n-gram fallback).

---

## 8. Feedback & Review

| Feature | API Method | Description |
|---|---|---|
| Record feedback | `ws.record_feedback(event)` | Immutable feedback event |
| Get review queue | `ws.get_review_queue()` | Pending dataset examples |
| Review example | `ws.review_example(example_id, accept, reviewer_id?)` | Accept/reject pending example |
| Export dataset | `ws.export_dataset(task_type, output_dir)` | Export accepted examples to JSONL |

---

## 9. Evaluation

| Feature | API Method | Description |
|---|---|---|
| Run benchmark | `ws.run_benchmark(benchmark_path, config?)` | Evaluate retrieval/QA on JSONL benchmark |

**Metrics**: precision@k, recall@k, MRR, latency.

---

## 10. Doctor / Diagnostics

| Feature | Source | Description |
|---|---|---|
| Environment check | `doctor_environment()` | Python version, core deps (pydantic, numpy, click), optional deps (torch, rasterio, txtai, llama-cpp, streamlit, etc.) |
| Workspace check | `doctor_workspace(path)` | Structural validation (marker file, DB, settings) |
| API round-trip | `doctor_workspace_open(path)` | Open → stats → close smoke test |

---

## 11. Vision / Image Search (Experimental)

| Feature | API Method | Description |
|---|---|---|
| Image index | `ws.image_index()` | Load/create `ImageIndex` manager |
| Search images | `ws.search_images(query_vector, top_k)` | Similarity search over vision-embedded raster tiles |

**Vision embedder**: `OlmoEarthVisionEmbedder` (OLMoEarth Nano v1.2, torch-native, `weights.pth`).

---

## 12. Supported Loaders & Parsers

| Format | Loader | Notes |
|---|---|---|
| PDF | `opendataloader_pdf` → `PdfLoader` (PyMuPDF fallback) | OpenDataLoader requires Java 11+ |
| DOCX | `DocxLoader` | python-docx |
| GeoTIFF | `GeoTiffLoader` | rasterio, generates tiles + preview |
| GeoJSON | `GeoJsonLoader` | shapely, bbox extraction |
| Code | `CodeLoader` | Python, JS, Jupyter |
| Text | `TextLoader` | TXT, MD, CSV |

---

## 13. Embedding Backends

| Backend | Description |
|---|---|
| `NumpyBackend` | Offline n-gram TF (always available) |
| `TxtaiBackend` | txtai ANN index (requires `txtai` extra) |
| `VectorBackend` | Persisted vector index (qdrant or file-backed) |

**Text embedders**: `NomicEmbedder` (GGUF), `SentenceTransformerEmbedder`, `HashEmbedder` (fallback).

**Vision embedders**: `OlmoEarthVisionEmbedder` (torch-native).

---

## 14. Vector Backends

| Backend | Description |
|---|---|
| `NumpyBackend` | In-process numpy vectors |
| `TxtaiBackend` | txtai ANN |
| `QdrantBackend` | Qdrant (local or remote, via `qdrant-client`) |

---

## API Surface Summary (for frontend design)

```
GeoMemory
├── .open(path) → GeoMemory
├── .create(path, config?) → GeoMemory
├── .close()
├── .settings → WorkspaceSettings
├── .update_settings(**kwargs) → WorkspaceSettings
├── .stats() → dict
│
├── .create_collection(name, description?) → Collection
├── .list_collections() → Collection[]
├── .get_collection(id) → Collection?
├── .archive_collection(id) → bool
│
├── .ingest(source, collection_id, parser?, index_after?) → Job
│
├── .search(query, mode, top_k, top_n, collections?, spatial?, temporal?, sensor?) → SearchResult
│
├── .ask(question, mode, collections?, filters?) → QAResult
│
├── .list_assets(collection_id?) → Asset[]
├── .inspect(asset_id) → AssetDetail
│
├── .build_index(space_id) → None
├── .rebuild_index(space_id) → None
│
├── .record_feedback(event) → FeedbackEvent
├── .get_review_queue() → DatasetExample[]
├── .review_example(example_id, accept, reviewer_id?) → bool
├── .export_dataset(task_type, output_dir) → Path
│
├── .run_benchmark(benchmark_path, config?) → BenchmarkResult
│
├── .image_index() → ImageIndex
├── .search_images(query_vector, top_k) → dict[]
│
└── .events → EventBus (domain events: asset_created, collection_created)
```

---

## Domain Events (for real-time UI updates)

| Event | Payload |
|---|---|
| `asset_created` | `revision_id`, `hash`, `mime_type`, `segment_count` |
| `collection_created` | `name`, `workspace_id` |

---

## Pydantic Models (JSON-serializable)

All models extend `GeoMemoryModel` with `model_dump(mode="json")` support:
- `WorkspaceConfig`, `WorkspaceSettings`
- `Collection`, `Asset`, `AssetRevision`, `AssetDetail`
- `Segment`, `SearchHit`, `SearchResult`, `SearchFilters`
- `SpatialFilter`, `TemporalFilter`
- `QAResult`, `Answer`, `Citation`
- `Job`, `FeedbackEvent`, `DatasetExample`
- `BenchmarkResult`, `EmbeddingRecord`

---

## Frontend Page Mapping (suggested)

| Page | Features |
|---|---|
| **Overview** | Stats dashboard, storage metrics, index status |
| **Collections** | List, create, archive, view assets |
| **Ingest** | File upload, format detection, progress, dedup notice |
| **Search** | Query bar, mode toggle, filter panel (spatial/temporal/sensor), results list with snippets |
| **Ask** | Chat interface, mode selector, citations display, abstention notice |
| **Assets** | List, inspect detail, view segments/scenes/layers |
| **Index** | Build/rebuild controls, space selector, progress |
| **Feedback** | Review queue, accept/reject, export |
| **Eval** | Benchmark upload, run, metrics display |
| **Settings** | Workspace config form, model paths, offline toggle |
| **Doctor** | Environment status, workspace health, API round-trip test |
