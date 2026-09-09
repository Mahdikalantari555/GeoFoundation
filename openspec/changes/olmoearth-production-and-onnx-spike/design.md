## Context

`OlmoEarthVisionEmbedder` (`embeddings/olmoearth_vision.py`) exists and works standalone. `ImageIndex` (`index/image_index.py`) persists embeddings on disk. `GeoTiffLoader` (`ingest/loaders/geotiff.py`) parses GeoTIFFs into scenes + tiles but never calls the vision embedder. The two tracks (production wiring and ONNX spike) are independent: track A extends existing code paths; track B is a research experiment that may or may not produce a usable artifact.

## Goals / Non-Goals

**Goals:**
- Wire OLMoEarth embedder into the GeoTIFF ingest pipeline so image embeddings are produced automatically when `vision_path` is configured.
- Persist those embeddings in `ImageIndex` under the existing space id.
- Run an ONNX export spike measuring quality, latency, and size deltas vs. native torch.

**Non-Goals:**
- Cross-modal text+image retrieval fusion (deferred to Change 3).
- Multi-model vision space management (only OLMoEarth Nano v1.2 for now).
- GPU acceleration — CPU-only inference throughout.
- ONNX as a runtime replacement for torch (only if spike confirms acceptable quality).

## Decisions

### D1. Embed at tile level, not full-scene level
Large GeoTIFFs are tiled during ingest (`rs/raster/tiler.py`). Embedding each tile independently keeps per-request memory bounded and matches the model's 128×128 patch training. The scene-level embedding (if needed) can be an average of tile embeddings computed later. For now, only tiles that have preview paths are embedded.

Alternative considered: embedding the full scene resized to 128×128. Rejected because it loses spatial resolution and the tiler already produces meaningful tile windows.

### D2. Embedding persistence in ImageIndex on ingest
`ImageIndex.save()` already supports persisting to a directory. The ingest pipeline will call `image_index.upsert(scene_id_or_tile_id, embedding)` after embed, then `image_index.save(index_dir)` to persist. This keeps the index in sync without a separate build step.

### D3. ONNX spike as a standalone script
The export script lives at `scripts/export_olmoearth_onnx.py` and the comparison benchmark at `scripts/benchmark_olmoearth_onnx.py`. Neither is imported by the library — they are developer tooling. This avoids adding ONNX as a dependency of the main package even in dev mode.

## Risks / Trade-offs

- [ONNX op support] → OLMoEarth's encoder may use ops not yet supported by ONNX export (e.g., custom attention patterns). Mitigation: spike documents failures explicitly; if export fails, track A proceeds with torch-only and Change 3 designs for one vision space.
- [Tile count explosion] → A large Sentinel-2 scene at 10 m resolution can produce thousands of 256×256 tiles. Mitigation: cap embeddings per ingest at a configurable `max_tiles_to_embed` (default 100); document in settings.
- [Ingest latency] → Vision embedding adds latency to GeoTIFF ingest. Mitigation: the embed step runs synchronously but is bounded by tile count cap; large scenes can be processed in a background job (future async work).

## Migration Plan

Track A is additive — no schema changes, no behavior change when `vision_path` is unset. Track B is purely experimental tooling with no production impact. Both tracks can be applied independently.

## Open Questions

- What is a reasonable default for `max_tiles_to_embed`? Proposed: 100. Depends on typical scene sizes in the user's workflow.
- Should the ONNX spike also test quantization (INT8) as a separate experiment, or stay at FP32/FP16 only? Recommendation: FP16 only for initial spike; INT8 is a follow-up if FP16 is viable.
