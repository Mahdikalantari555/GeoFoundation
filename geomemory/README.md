# GeoMemory

A multimodal, spatiotemporal knowledge engine for remote sensing research.

GeoMemory is a local-first Python library that ingests documents, code, satellite imagery, spectral features, and vector data into a unified, searchable memory — with explicit spatial, temporal, sensor, and provenance metadata.

## Highlights

- **Local-first & offline**: everything runs on your machine. No cloud dependencies, no telemetry by default.
- **Hybrid search**: sparse (FTS5) + dense (vector) search fused with Reciprocal Rank Fusion, with metadata/spatial/temporal filters.
- **Grounded QA**: answers with citations into the exact source location, abstention when evidence is insufficient.
- **Multimodal**: text, code, and (optional) satellite imagery embedding in isolated embedding spaces.
- **Structurally-aware ingestion**: header-then-token chunking, AST-based code parsing, GeoTIFF metadata/spectral indices.
- **Traceable provenance**: SHA-256 content-addressed storage, immutable revisions, full retrieval run logs.
- **Feedback & evaluation**: raw feedback events → review queue → versioned dataset export (RAG eval / QA eval / SFT / preference).

## Installation

```bash
pip install -e ".[dev]"
```

Optional dependency groups:

```bash
pip install -e ".[ai]"      # txtai + llama-cpp-python (retrieval/inference stack)
pip install -e ".[st]"      # sentence-transformers (dense text embeddings)
pip install -e ".[vector]"  # qdrant-client (server-mode vector backend)
pip install -e ".[docs]"    # PDF/DOCX parsing
pip install -e ".[rs]"      # rasterio/shapely/geopandas (remote sensing)
pip install -e ".[ui]"      # Streamlit reference app
```

## Settings

Workspace settings are persisted in `workspace.yaml` and can be overridden via environment variables:

| Variable | Setting | Default |
|---|---|---|
| `GEOMEMORY_QDRANT_URL` | `qdrant_url` | (unset = local backend) |
| `GEOMEMORY_ST_MODEL` | `st_model_name` | `sentence-transformers/all-MiniLM-L6-v2` |
| `GEOMEMORY_EMBEDDING_BACKEND` | `embedding_backend` | `hashing` |
| `GEOMEMORY_VECTOR_BACKEND` | `vector_backend` | `local` |

## Docker

A multi-stage `Dockerfile` and `docker-compose.yml` package GeoMemory with Qdrant:

- **CLI target** — installs the package plus AI/vector extras; entrypoint `geomemory`.
- **UI target** — adds Streamlit and serves the reference app on port 8501.

```bash
docker build --target cli -t geomemory:cli .
docker compose up
```

The compose stack starts Qdrant (named volume) and the UI, pre-wired so the app connects to Qdrant by service name. Volumes:

- `qdrant_storage` — Qdrant data (survives recreation).
- `workspace_data` — GeoMemory workspace.
- `hf_cache` — Hugging Face model cache (avoids re-downloading the embedding model).

## Quickstart

```python
from geomemory import GeoMemory

memory = GeoMemory.open("./workspace")

collection = memory.create_collection("papers", "Remote sensing papers")
job = memory.ingest("paper.pdf", collection_id=collection.id)
memory.build_index("text.nomic.v1")

results = memory.search("crop stress detection with vegetation indices")
answer = memory.ask("What vegetation indices detect crop stress?")
print(answer.text)
for citation in answer.citations:
    print(citation.locator)
```

### Remote sensing (raster / vector, Phase 2)

```python
from geomemory import GeoMemory
from geomemory.core.models import SpatialFilter, TemporalFilter

memory = GeoMemory.open("./workspace")
col = memory.create_collection("imagery", "Satellite imagery and vector layers")

# Ingest a GeoTIFF scene and a GeoJSON vector layer (requires `.[rs]`).
memory.ingest("scene.tif", collection_id=col.id)
memory.ingest("fields.geojson", collection_id=col.id)

# Filter by location (EPSG:4326 lon/lat bbox), acquisition window, or sensor.
results = memory.search(
    "Sentinel-2 flood extent",
    spatial=SpatialFilter(bbox=(51.0, 35.0, 52.0, 36.0)),
    temporal=TemporalFilter(field="acquired_at", from_="2024-01-01", to="2024-12-31"),
    sensor=["Sentinel-2"],
)

# Spectral indices are pure numpy and testable without rasterio.
from geomemory.rs.raster.spectral import ndvi
# ndvi_result = ndvi(nir_array, red_array)   # (NIR - RED) / (NIR + RED)

# Experimental image search over vision-embedded tiles (needs OLMoEarth GGUF).
# index.save(memory.index_dir / "image", manifest)
# hits = memory.search_images(query_vector)
```

Spatial/temporal/sensor filters work offline in `memory.search()`; GeoTIFF/GeoJSON ingestion and spectral computations require the optional `.[rs]` dependencies (rasterio, shapely, geopandas, Pillow).

## CLI

```
geomemory init PATH
geomemory doctor [--workspace PATH]      # environment + workspace diagnostics
geomemory ingest SOURCE --collection NAME
geomemory index build --space SPACE_ID
geomemory search QUERY [--format table|json|markdown]
geomemory ask QUESTION
geomemory chat
geomemory app
geomemory inspect ASSET_ID
geomemory eval run BENCHMARK_PATH
geomemory feedback export --type TYPE
```

## Dashboard

A Streamlit reference app consuming only the public `GeoMemory` API:

```bash
streamlit run apps/dashboard/app.py
```

The sidebar opens or creates a workspace (path from `GEOMEMORY_DASHBOARD_ROOT` or `./workspace`). Pages: overview, search, ask, assets, ingest, feedback, evaluation, settings.

## Development

```bash
pytest tests/
pytest --cov=geomemory --cov-report=term-missing
mypy --strict src/geomemory
ruff check src/ tests/
```

## License

MIT

## Project Status

GeoMemory is in **alpha**. APIs may change between releases.

## Contributing

This project follows a spec-driven workflow. Requirements and changes are managed via the `openspec` CLI (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`).

1. Propose a change with `/opsx:propose` (creates proposal + specs + design + tasks).
2. Implement the approved change with `/opsx:apply`.
3. Finalize and archive with `/opsx:archive`.

Development setup:

```bash
conda activate ai
pip install -e ".[dev,ai,docs,rs,ui]"
pytest tests/
mypy --strict src/geomemory
ruff check src/ tests/
```