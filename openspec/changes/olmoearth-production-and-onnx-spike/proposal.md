## Why

The OLMoEarth vision embedder works in isolation but is not wired into the default ingestion pipeline: GeoTIFF ingest produces scene metadata and tiles but never calls the vision embedder, so no satellite images are searchable by visual similarity. Additionally, the ONNX export path for OLMoEarth is unexplored — if feasible, it would let GeoMemory keep its local-first lightweight philosophy (no torch at runtime) while still using foundation-model representations. Both tracks must be completed before unified multimodal retrieval (Change 3) can be designed with confidence about how many embedding spaces exist.

## What Changes

- **Track A (production):** Wire `OlmoEarthVisionEmbedder` into the GeoTIFF ingestion pipeline so every ingested raster scene auto-generates an embedding stored in `image.olmoearth-nano-v12.v1`. The dashboard's image-search page surfaces these results.
- **Track B (ONNX spike):** Export OLMoEarth Nano v1.2 from `.pth` to ONNX format; measure inference latency, model size, and embedding quality delta vs. native torch. Outcome determines whether a second vision space (`image.olmoearth.onnx.v1`) is added to the architecture.
- The existing `vision-embedding` spec is extended to require vision embedder invocation during raster ingest (track A).
- Track B is intentionally scoped as an experiment: if ONNX export fails or degrades quality below acceptability, the spike documents the failure and the architecture keeps torch as the sole vision path.

## Capabilities

### New Capabilities
- `vision-ingestion-production`: GeoTIFF ingest automatically produces OLMoEarth embeddings when `vision_path` is configured; search page surfaces image-similarity results.
- `onnx-export-spike`: Experimental ONNX export of OLMoEarth Nano v1.2 with measured latency/quality deltas vs. native torch.

### Modified Capabilities
- `vision-embedding` (geomemory): extends requirement to mandate embedder invocation during raster ingest when configured.

## Impact

- **Code**: `src/geomemory/ingest/loaders/geotiff.py` (call embedder post-persist); `src/geomemory/index/image_index.py` (persist on ingest); `scripts/export_olmoearth_onnx.py` (spike); `apps/web/src/features/maps/` or new image-search page.
- **APIs**: Additive — no changes to existing endpoints; new search mode `mode="image"` or visual-similarity filter on search results.
- **Deps**: Track A adds no new deps (`torch` already in `[vision]` extra). Track B may add `onnx` as an optional export-tool dep (not a runtime dep).
- **Risks**: ONNX export may not preserve band-padding logic (`_TARGET_CHANNELS = 12`); spike must validate exported model produces comparable embeddings.
