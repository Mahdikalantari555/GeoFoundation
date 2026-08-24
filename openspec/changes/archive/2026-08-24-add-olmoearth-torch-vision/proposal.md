# Proposal: add-olmoearth-torch-vision

## Why

GeoMemory's vision embedding path is a placeholder: `PlaceholderVisionEmbedder` always raises, and the only experimental implementation (`LlamaCppVisionEmbedder`) requires a GGUF checkpoint via llama-cpp-python. The user's real OLMoEarth v1.2 Nano checkpoint is a native PyTorch state dict (`weights.pth`, ~16 MB), which the GGUF path can never load. A working image-embedding backend unlocks the existing but dormant multimodal story (raster tiles → embeddings → similarity search) and strengthens the thesis demo (satellite imagery becomes searchable alongside documents and code).

## What Changes

- Add a new torch-native embedder `OlmoEarthVisionEmbedder` in `src/geomemory/embeddings/olmoearth_vision.py` implementing the existing `VisionEmbedder` protocol: loads an OLMoEarth v1.2 Nano `.pth` state dict directly (no llama.cpp, no GGUF), lazy-imports torch, embeds images/tiles into L2-normalized float32 vectors.
- Weight-loading adapter follows the reference implementation pattern from the user's local benchmark project (`eurocrop-olmoearth-benchmark/src/models/olmoearth.py`): build the Nano backbone from its config, load the state dict with `torch.load(..., map_location="cpu")`, run forward passes under `torch.inference_mode()`.
- Wire settings: reuse the existing `WorkspaceSettings.vision_path` field, add env-var override `GEOMEMORY_VISION_PATH`, and add an `IndexService`-style factory so callers get `OlmoEarthVisionEmbedder(vision_path)` instead of the placeholder when a path is configured.
- New optional dependency extra `[vision]` (`torch>=2.0` CPU — shares the wheel already pulled by `[st]`; no new heavy unique dep).
- Doctor reports vision-model availability: whether `torch` is importable and whether the configured `vision_path` exists on disk.
- Keep `LlamaCppVisionEmbedder` untouched for backward compatibility; it is no longer the default recommendation. `PlaceholderVisionEmbedder` remains the fallback when no path is configured.
- Out of scope (phase 2): automatic raster-tile ingestion pipeline wiring (GeoTIFF ingest → tiler → vision index build → `search_images` end-to-end command/dashboard UI). This change delivers the working embedder + config seam + doctor; pipeline integration builds on it next.

## Capabilities

### New Capabilities
- `vision-embedding`: image embedding via OLMoEarth v1.2 Nano torch weights — model loading contract, input/output contract (paths/bytes/PIL → L2-normalized vectors), space isolation, settings/env configuration, graceful degradation without torch or without a configured path, doctor visibility.

### Modified Capabilities
- None. Existing specs are unaffected: the placeholder behavior stays as the documented no-config default, and no retrieval/QA requirement changes.

## Impact

- **Code**: new `embeddings/olmoearth_vision.py`; small edits to `core/config.py` (env override), `services/index_service.py` or a new factory helper (embedder selection), `services/doctor.py` (vision check); export updates in `embeddings/__init__.py`.
- **APIs**: none broken. Public surface gains one exported class; facade unchanged.
- **Dependencies**: new `[vision]` extra pinning `torch>=2.0`; torch already present transitively via `[st]` (sentence-transformers). No CUDA requirement — CPU inference is sufficient for Nano (~16 M params).
- **Operational**: first model load reads a local `.pth` file only — fully offline, no network, no JVM, no llama.cpp runtime.
- **Tests**: unit tests with a stubbed torch module (fake nn.Module + tiny random state dict) covering load, embed shape/dtype/normalization, error paths (missing extra, missing path, corrupt checkpoint), and doctor reporting. No GPU required.
