# GeoMemory — lightweight, local-first geospatial memory

Local-first Python library for ingesting documents, code, GeoTIFF, and vector data into a hybrid searchable memory (FTS5 sparse + dense cosine) with citations, provenance, and geospatial filters. **No torch/txtai by default** — dense text runs on `onnxruntime` + quantized `Xenova/all-MiniLM-L6-v2` (384-d) inside SQLite via `sqlite-vec`.

Highlights: offline by default, RRF hybrid, RAG with abstention, isolated embedding spaces, SHA-256 content addressing, feedback → dataset export.

## Architecture (v0.2 lightweight refactor)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10+, Pydantic v2, SQLite WAL+FTS5+RTree | single writer, file-first backup (`cp -r workspace`) |
| Text embeddings | **ONNX** `onnxruntime` + `tokenizers` + `huggingface_hub` → `Xenova/all-MiniLM-L6-v2` `onnx/model_quantized.onnx`, 384-d, mean-pool over `attention_mask`, L2 | CPU-only, no torch, <200 MB base |
| Provider seam | `EmbeddingProvider` (`ONNXEmbeddingProvider` canonical, stubs `OpenAI/Voyage/Custom`) via `embeddings/factory.py:build_text_embedder` | callers depend on protocol, not inference |
| Vector store | **sqlite-vec** `vec0` virtual table per `space_id` (`vec_text_onnx_...`), cosine; `QdrantBackend`/`LanceBackend` pluggable; `NumpyBackend` fallback | embedded, no server, backup stays with `geomemory.db` |
| Lexical | `segments_fts` (FTS5, `unicode61 remove_diacritics`) + triggers | keyword/BM25/phrase |
| Fusion | `retrieval/fusion.rrf_fuse` + `search_service.apply_hit_filters` (spatial/temporal/sensor) | single canonical path, `Workspace.search` reuses it |
| QA | `LLMBackend` protocol (`LlamaCppBackend` + `ApiLLMBackend`) | grounded answers with citations + abstention |
| Vision | `OlmoEarthVisionEmbedder` behind opt-in `[vision]` (`torch`) | image path stays torch-free unless opted in |

Embedding spaces isolated: `text.*` vs vision; `text.onnx.<safe>.v1` per model, never mixed.

## Installation

Base install is torch-free:

```bash
# conda env geospatial (preferred)
conda run -n geospatial uv pip install -e libs/geomemory
# or
pip install geomemory
# pipdeptree | grep -qi torch → no matches (CI gate)
```

Optional groups:

```bash
pip install -e ".[docs]"          # pymupdf, python-docx
pip install -e ".[rs]"            # rasterio, shapely, geopandas, Pillow
pip install -e ".[vector]"        # qdrant-client (server)
pip install -e ".[lancedb]"       # pylancedb (embedded LanceDB)
pip install -e ".[vision]"        # torch + olmoearth-pretrain (ONLY torch entry)
pip install -e ".[llamacpp]"      # llama-cpp-python (GGUF offline)
pip install -e ".[onnx]"          # alias — onnxruntime/tokenizers/sqlite-vec already in base
pip install -e ".[ui]"            # streamlit dashboard (legacy, optional — prefer gateway+web)
pip install -e ".[dev]"           # pytest/mypy/ruff
```

Base deps: `pydantic, numpy, click, PyYAML, onnxruntime>=1.18, tokenizers>=0.15, huggingface-hub>=0.23, sqlite-vec>=0.1.6`. No `txtai/torch/sentence-transformers/accelerate/safetensors`.

## Settings & env overrides

`workspace.yaml` persisted via `WorkspaceSettings` (`core/models.py`); env vars override:

| Variable | Setting | Default |
|---|---|---|
| `GEOMEMORY_EMBEDDING_PROVIDER` | `embedding_provider` (`onnx/openai/voyage/custom/hashing/llama-cpp`) | `onnx` |
| `GEOMEMORY_EMBEDDING_BACKEND` | `embedding_backend` (deprecated alias) | `hashing` |
| `GEOMEMORY_ONNX_MODEL` | `onnx_model_name` | `Xenova/all-MiniLM-L6-v2` |
| `GEOMEMORY_EMBEDDING_ROOT` | `embedding_path` (hub root) | `~/.cache/huggingface` via `EmbeddingModelHub` scan (`/mnt/data/LocalAI/Models/Embedding` → `workspace/indexes`) |
| `GEOMEMORY_VECTOR_BACKEND` | `vector_backend` (`sqlite-vec/lancedb/qdrant/numpy`) | `sqlite-vec` |
| `GEOMEMORY_QDRANT_URL` | `qdrant_url` | (unset) |
| `GEOMEMORY_ST_MODEL` | `st_model_name` (deprecated, mapped to Xenova) | `sentence-transformers/all-MiniLM-L6-v2` |
| `GEOMEMORY_VISION_PATH` | `vision_path` | (unset) |
| `GEOMEMORY_LLM_*` | `llm_provider/base_url/key_env/model_id/context_window` | `kilo-auto/free`, 32768 |

Offline: `offline=true` refuses network downloads (hub `EmbeddingUnavailableError` → `503 embedding_unavailable`).

## Quickstart

```python
from geomemory import GeoMemory

ws = GeoMemory.create("./workspace", name="demo")
col = ws.create_collection("papers", "RS papers")
ws.ingest("paper.pdf", collection_id=col.id)

# Dense index via ONNX sqlite-vec (auto-downloads Xenova quantized on first use when offline=false)
ws.build_index("text.onnx.Xenova-all-MiniLM-L6-v2.v1")
# Or wrapper: ws.rebuild_index(space_id) / build_index handles hashing/onnx via provider
results = ws.search("crop stress with NDVI", mode="hybrid", top_k=5)
print(results.hits[0].text, results.hits[0].score)

answer = ws.ask("What indices detect crop stress?")
print(answer.text, answer.citations[0].locator if answer.citations else "abstained")

# CLI
# geomemory init ./workspace
# geomemory ingest paper.pdf --collection papers
# geomemory index build --space text.onnx.Xenova-all-MiniLM-L6-v2.v1
# geomemory search "crop stress"
# geomemory reindex --workspace ./workspace --model Xenova/all-MiniLM-L6-v2
# geomemory doctor --workspace ./workspace
```

Raster/vector filtering (requires `[rs]`):
```python
from geomemory.core.models import SpatialFilter, TemporalFilter
results = ws.search(
    "Sentinel-2 flood",
    spatial=SpatialFilter(bbox=(51,35,52,36)),
    temporal=TemporalFilter(field="acquired_at", from_="2024-01-01", to="2024-12-31"),
    sensor=["Sentinel-2"],
)
```

## Storage layout

```
workspace/
  geomemory.db          # WAL, FTS5, RTree, sqlite-vec vec_* tables, manifests
  workspace.yaml        # WorkspaceSettings
  indexes/<space_id>/manifest.json  # space_id, model_id, dimension=384, checksum
  objects/<sha256>      # content-addressed blobs
  assets/{documents,code,imagery,vectors}
```

## Provider & retrieval

- `ONNXEmbeddingProvider` (`embeddings/provider.py`) wraps `OnnxTextEmbedder` (tokenizer.json + `onnx/model_quantized.onnx` preferred, fallback `onnx/model.onnx` etc., `CPUExecutionProvider`, mean-pool, L2, e5 prefix `query:/passage:`).
- `SqliteVecBackend` (`index/sqlite_vec_backend.py`) — per-space `vec_<safe>` (`embedding float[384] distance_metric=cosine` + `id TEXT PRIMARY KEY, chunk_text, metadata`), `serialize_float32`, `MATCH ? AND k=? ORDER BY distance`, score `1-distance`.
- `LanceBackend`/`QdrantBackend` behind `StorageBackend` protocol; no caller imports `lancedb/qdrant_client` outside `index/`.

## Migration from txtai/ST

```bash
pip uninstall -y txtai torch sentence-transformers  # or fresh venv
pip install geomemory              # base no longer pulls them
# Optional: pip install "geomemory[vision]" only if you need OLMoEarth
geomemory reindex --workspace ./workspace --provider onnx --model Xenova/all-MiniLM-L6-v2
# or: geomemory index reindex -w ./workspace --provider onnx
pipdeptree | grep -qi torch && echo "still have torch!" || echo "clean"
```

Manifests with `space_id=text.st.*` / `text.txtai.*` now warn `ReindexRequired`.

## CLI

```
geomemory init PATH
geomemory ingest SOURCE --collection NAME
geomemory index build --space SPACE_ID     # dense build
geomemory index rebuild --space SPACE_ID
geomemory index reindex -w WS --provider onnx --model Xenova/all-MiniLM-L6-v2
geomemory reindex -w WS --provider onnx    # top-level alias
geomemory search QUERY [--mode hybrid|sparse|dense]
geomemory ask QUESTION
geomemory chat / app (legacy) / inspect / eval / feedback / doctor
```

## Testing & quality gates

```bash
conda run -n geospatial pytest libs/geomemory/tests -q  # 345 passed, 9 skipped svc gates
conda run -n geospatial pytest libs/geomemory/tests/unit/test_provider.py libs/geomemory/tests/unit/test_sqlite_vec_backend.py -v
conda run -n geospatial python -c "import geomemory; assert 'torch' not in str(__import__('importlib.metadata').metadata('geomemory').get_all('Requires-Dist'))"
conda run -n geospatial pipdeptree | grep -qi torch && exit 1 || echo "no torch"
ruff check libs/geomemory/src
mypy --strict libs/geomemory/src  # pre-existing 81 legacy errors allowed (AGENTS.md)
```

`scripts/check_no_torch_dep.py` enforces the graph in CI.

## Docs & spec

- `openspec/` — authoritative specs + changes (`remove-txtai-torch-lightweight-retrieval` is the lightweight refactor).
- `docs/current-state/` — generated audit; `openspec/specs/` — as-is capability specs.
- Change workflow: `proposal → apply → archive`.

## License

MIT — alpha `0.1.0`, APIs may still change.
