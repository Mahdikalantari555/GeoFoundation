# Components (summary)

Full detail: [current-state/components.md](current-state/components.md).

| Package | Responsibility | Key units |
|---|---|---|
| `core/` | models, facade, config, events, hashing, registries | `GeoMemory` facade, 30+ Pydantic models, `EventBus`, `Registry[T]` |
| `ingest/` | parse & chunk sources into segments | loaders (text/code/pdf/geojson/geotiff), chunkers (fixed_size/header_then_token), `IngestionPipeline`, DB-backed `JobQueue` |
| `embeddings/` | text/vision vector producers | GGUF embedders (nomic / olmoearth), hashing fallback, protocols |
| `index/` | vector storage & search | numpy / txtai / persisted `VectorBackend`, `ImageIndex`, manifests |
| `retrieval/` | query understanding & result assembly | QueryParser, RRF fusion, dedup/diversity, spatial/temporal/sensor filters, context packer |
| `qa/` | grounded generation | ChatService, prompt modes, citation mapping/validation, abstention, llama.cpp backend |
| `rs/` | remote-sensing domain | raster reader/tiler/preview/spectral (NDVI/EVI), vector reader, spatial persistence |
| `storage/` | persistence | SQLite connect/migrate, ObjectStore, 7 repositories, schema.sql v1 |
| `feedback/` | human signal → training data | label builders, dedup, review queue, 4 dataset exporters |
| `eval/` | quality measurement | recall/precision/MRR/nDCG, QA metrics, benchmark runner/reporter |
| `services/` | orchestration wrappers | index/ingestion/search/chat/feedback/job services, doctor |
| `cli/` | command surface | `geomemory` group, 10 commands, lazy imports |

Apps: `apps/dashboard/` (canonical UI, public-API-only), `apps/app.py` (legacy). Workspace on disk = `workspace.yaml` + `geomemory.db` + `objects/` + indexes.
