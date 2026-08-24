# API Inventory — Current State

Status: as-is, v0.1.0.

## 1. Public Python API (`import geomemory`)

Exports (`src/geomemory/__init__.py`): `__version__`, facade `GeoMemory`, 8 exceptions, 17 domain models. Nothing else is public contract; the dashboard consumes exactly this surface.

### Facade `GeoMemory` (class `Workspace` in `core/workspace.py`)

| Method | Signature (abridged) | Behavior |
|---|---|---|
| `open` | `(cls, path) -> GeoMemory` | Open existing workspace dir |
| `create` | `(cls, path, config: WorkspaceConfig \| None) -> GeoMemory` | Create new workspace |
| `settings` / `update_settings` | property / `(**changes) -> WorkspaceSettings` | Read/write workspace.yaml config |
| `create_collection` | `(name, description="") -> Collection` | |
| `list_collections` | `() -> list[Collection]` | |
| `get_collection` | `(collection_id) -> Collection \| None` | |
| `archive_collection` | `(collection_id) -> bool` | |
| `ingest` | `(source: str\|Path\|bytes, collection_id, *, parser=None, index_after=True) -> Job` | Full sync pipeline; dedups by SHA-256 |
| `search` | `(query, *, mode="hybrid", top_k=20, top_n=5, collections=None, spatial=None, temporal=None, sensor=None) -> SearchResult` | Hybrid RRF retrieval + filters |
| `ask` | `(question, *, mode="grounded_qa", top_k=?, collection_ids=None, ...) -> QAResult` | Grounded QA w/ citations & abstention |
| `build_index` / `rebuild_index` | `(space_id) -> dict` | Embed all segments → backend → manifest |
| `record_feedback` | `(event: FeedbackEvent) -> FeedbackEvent` | Append feedback event (+dataset example path) |
| `get_review_queue` | `() -> list[DatasetExample]` | Pending review items |
| `review_example` | `(example_id, accept, reviewer_id=None) -> bool` | Accept/reject |
| `export_dataset` | `(task_type, output_dir) -> Path` | rag_eval/qa_eval/sft/preference export |
| `run_benchmark` | `(benchmark_path, config=None) -> BenchmarkResult` | Eval runner entry |
| `list_assets` | `(collection_id=None) -> list[Asset]` | |
| `inspect` | `(asset_id) -> AssetDetail` | Asset + revision + segment summary |
| `stats` | `() -> dict[str, Any]` | Workspace counters |
| `image_index` | property — lazy `ImageIndex` | Vision embedding index |
| `search_images` | `(query_vector, *, top_k=10) -> list[dict]` | Experimental image search |

Also usable directly (stable sub-APIs): `retrieval.search_service.SearchService`, `qa.chat_service.ChatService`, `ingest.pipeline.IngestionPipeline`, `ingest.job_queue.JobQueue`, `services.*` wrappers, `rs.raster.spectral.ndvi/evi/compute_index`, `storage.*`.

### Exceptions
`GeoMemoryError` ← `WorkspaceNotFoundError`, `CollectionNotFoundError`, `AssetNotFoundError`, `UnsupportedFormatError`, `DatabaseError`, `ModelNotLoadedError`, `NetworkDisabledError`, `AbstentionError`.

## 2. CLI — `geomemory` (entry point `cli.main:cli`)

| Command | Options / args | Purpose |
|---|---|---|
| `init PATH` | `--name`, `--offline/--no-offline` (default offline), `--language en\|fa` | Create workspace |
| `doctor [-w PATH]` | | Environment + workspace diagnostics |
| `ingest SOURCE -c NAME [--no-index] [-w PATH]` | source must exist | Ingest file into named/id collection |
| `index build [--space ID] [-w PATH]` · `index rebuild [--space ID]` | default space `text.nomic.v1` | Build/rebuild vector index |
| `search QUERY [--mode sparse\|dense\|hybrid] [--top-k N] [--top-n N] [-c ID ...] [--format table\|json\|markdown] [-w PATH]` | | Run search |
| `ask QUESTION [-w PATH] [--mode grounded_qa\|research\|code]` | | Grounded QA to stdout |
| `chat [-w PATH] [--mode ...]` | | Interactive REPL |
| `app [-w PATH]` | | Launch Streamlit UI |
| `inspect ASSET_ID [-w PATH]` | | Print asset detail |
| `eval run BENCHMARK_PATH [--config JSON] [-w PATH]` | | Benchmark + report |
| `feedback export --type rag_eval\|qa_eval\|sft\|preference [--output DIR] [-w PATH]` · `feedback review [--pending]` | | Dataset export / review queue listing |

Commands import lazily so CLI startup doesn't pull heavy deps. Version via `--version` (0.1.0).

## 3. Dashboard pages (`apps/dashboard/`)

Entry `streamlit run apps/dashboard/app.py`; workspace root from `GEOMEMORY_DASHBOARD_ROOT` or `./workspace`. Pages: **overview** (stats), **search** (hybrid search UI), **ask** (QA with citations), **assets** (list/inspect), **ingest**, **feedback** (review queue), **eval** (benchmark runner/report), **settings**. All data access through `lib.get_workspace()` → public API only.

## 4. What does not exist

- No HTTP/REST/gRPC server, no MCP server, no WebSocket API.
- No authentication/authorization layer.
- No background worker process for jobs.
- No plugin loading from external packages (registries are in-process only).
