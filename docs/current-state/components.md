# Component Map — Current State

Status: as-is, `main` @ `364b897`.

## `src/geomemory/` — 12 packages

### core/ — domain models & workspace lifecycle
| Unit | Responsibility |
|---|---|
| `models.py` (691 LOC) | All Pydantic v2 domain models: `Workspace`, `Collection`, `Asset`, `AssetRevision`, `Segment`, `RasterScene`, `RasterTile`, `VectorLayer`, `Observation`, `EmbeddingRecord`, `Relation`, `Conversation`, `Turn`, `RetrievalRun`, `Answer`, `Citation`, `SearchHit/Result/Filters`, `QAResult`, `FeedbackEvent`, `DatasetExample`, `Job`, plus drafts (`ParsedObject`, `SegmentDraft`, `IndexRecord`, `SourceRef`) and eval models |
| `workspace.py` (1152 LOC) | **The facade.** `Workspace` class + `GeoMemory` subclass: open/create, collections, ingest, search, ask, index build/rebuild, feedback/review/export, benchmark, inspect/stats, image search |
| `config.py` | `WorkspaceSettings` load/save to `workspace.yaml` |
| `events.py` | `DomainEvent`, in-process `EventBus` (subscribe/emit) |
| `exceptions.py` | Hierarchy rooted at `GeoMemoryError` (8 public exceptions) |
| `hashing.py` | SHA-256 bytes/file; `hash_object_path()` 3-level shard layout |
| `plugin_registry.py` | Generic `Registry[T]`; loader/chunker/embedder/backend registries |

### ingest/
| Unit | Responsibility |
|---|---|
| `loaders/base.py` | `Loader` protocol, `LoaderRegistry` |
| `loaders/text.py · code.py · pdf.py · geojson.py · geotiff.py` | Text, AST-aware code, PDF (pymupdf), GeoJSON, GeoTIFF parsing → chunks + spatial payload |
| `chunkers/fixed_size.py · header_then_token.py` | Token-window chunking; heading-preserving chunking for documents |
| `pipeline.py` | `IngestionPipeline.ingest_source()/ingest_batch()`: resolve loader → parse → attach spatial metadata → persist via repos |
| `job_queue.py` | DB-backed `JobQueue`: submit/get/list/update/complete/fail/cancel/run |

### embeddings/
| Unit | Responsibility |
|---|---|
| `text_embedder.py` / `vision_embedder.py` | Protocols (`TextEmbedder`, `VisionEmbedder`) + `PlaceholderVisionEmbedder` |
| `hashing_text.py` | Dependency-free n-gram hashing embedder (fallback/dev) |
| `llama_cpp_text.py` | GGUF text embeddings, model id default `nomic-embed-text-v2-moe` |
| `llama_cpp_vision.py` | GGUF vision embeddings, model id default `olmoearth-nano` (experimental) |
| `normalization.py` | L2 normalization helpers |

### index/
| Unit | Responsibility |
|---|---|
| `backend.py` | `RetrievalBackend` protocol: upsert/search/delete/rebuild/count |
| `numpy_backend.py` | Pure-numpy term-frequency cosine backend; buildable from database |
| `vector_backend.py` | Persisted dense vector backend with save/load + manifest integration |
| `txtai_backend.py` | txtai embeddings backend (optional `ai` extra) |
| `image_index.py` | Cosine image index over vision embeddings; save/load with manifest |
| `manifest.py` | `IndexManifest` read/write per index dir |

### retrieval/
| Unit | Responsibility |
|---|---|
| `query_parser.py` | Query cleaning, filter extraction, intent detection |
| `fusion.py` | `rrf_fuse()` and `linear_fuse()` rank fusion |
| `deduplicator.py` | Exact dedup + per-document diversity cap |
| `spatial_filter.py` / `temporal_filter.py` | Bbox intersect / time-window post-filtering on hits |
| `search_service.py` | Orchestration: parse → multi-backend search → fuse → dedup → diversity → filters → top_n; records `RetrievalRun` |
| `context_packer.py` | Packs search hits into token-budgeted LLM context |

### qa/
| Unit | Responsibility |
|---|---|
| `backend.py` | `LLMBackend` protocol + `NullBackend` (abstains) |
| `llama_cpp_backend.py` | GGUF generation backend (default model id `minicpm`) |
| `prompts.py` | Grounded-QA / research / code prompt builders |
| `citation.py` | `[n]` key extraction → citation mapping to source segments; validation |
| `abstention.py` | Abstention detection & reason classification |
| `chat_service.py` | `ChatService.ask()`: retrieve → prompt → generate → citations → abstain check → persist conversation turn/answer |

### rs/ — remote sensing
| Unit | Responsibility |
|---|---|
| `raster/reader.py · metadata.py` | rasterio window reads; scene metadata extraction (CRS EPSG-checked, bbox, transform) |
| `raster/tiler.py` | Scene tiling with window metadata |
| `raster/preview.py` | PNG preview generation (Pillow) |
| `raster/spectral.py` | `ndvi`, `evi`, band statistics, band mapping validation, `compute_index` |
| `vector/reader.py` | GeoJSON/vector layer reading (geopandas/shapely) |
| `persist.py` | `persist_scene()` / `persist_vector_layer()` → DB rows + RTree entries |

### services/ — thin orchestration wrappers
`IndexService` (embed all segments → upsert backend → manifest), `IngestionService` (submit ingestion jobs async-shaped), `search_service.SearchService` / `chat_service.ChatService` (facade delegates), `FeedbackService`, `JobService`, `doctor.py` (environment + workspace diagnostics).

### eval/, feedback/, storage/, cli/
- **eval/**: retrieval metrics (`recall@k`, `precision@k`, `mrr@k`, `ndcg@k`), QA metrics (`abstention_accuracy`, `citation_correctness`, `faithfulness_proxy`, `abstain_rate`), `BenchmarkRunner`, JSONL benchmark loader, JSON/markdown reporter.
- **feedback/**: label builders (rating, source relevance, edited answer, preferred sources), dataset example construction, duplicate grouping, `ReviewQueue`, exporters for `rag_eval` / `qa_eval` / `sft` / `preference`, dataset card generator.
- **storage/**: `database.connect()` (WAL, FK), schema init from `schema.sql`, integrity checks, migration registry (`Migration` dataclass, version table), `ObjectStore` (put/get/delete by hash), 7 repositories.
- **cli/**: Click group with lazy command registration.

## Apps & scripts

| Path | Role |
|---|---|
| `apps/dashboard/` | Current Streamlit reference app: pages overview/search/ask/assets/ingest/feedback/eval/settings; `lib.py` session helpers, public-API-only rule |
| `apps/app.py` | Legacy single-page Streamlit demo (superseded by dashboard) |
| `scripts/spike_txtai_embedding.py` | txtai spike validation (pytest marker `spike`) |
| `scripts/run_phase1_benchmark.py` | Retrieval phase-1 benchmark driver |

## Workspace directory layout (on disk)

```
workspace/
├── workspace.yaml      # WorkspaceSettings (models paths, offline flag, language)
├── geomemory.db        # SQLite (WAL; -wal/-shm alongside)
└── objects/            # content-addressed blobs: ab/cd/<sha256>
```
