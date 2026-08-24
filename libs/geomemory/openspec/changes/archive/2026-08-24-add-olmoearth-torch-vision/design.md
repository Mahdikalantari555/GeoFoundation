# Design: add-olmoearth-torch-vision

## Context

The vision path is the last dormant capability: protocol exists (`VisionEmbedder`), `ImageIndex` (numpy cosine, persisted) exists, but no real embedder ships. The only implementation targets GGUF/llama.cpp; the actual asset is a native `.pth` state dict. A working reference loader exists in the user's local benchmark project (`eurocrop-olmoearth-benchmark/src/models/olmoearth.py`), which builds the Nano backbone and loads weights via torch + transformers utilities — this change mirrors that approach inside GeoMemory without depending on the benchmark repo.

## Goals / Non-Goals

- Goals:
  - Load OLMoEarth v1.2 Nano `weights.pth` directly on CPU; embed images to L2-normalized float32 vectors.
  - Config seam via existing `WorkspaceSettings.vision_path` + new env override.
  - Zero impact on text paths; no llama.cpp involvement anywhere in the new code.
- Non-Goals:
  - End-to-end raster ingest→tile→index→search pipeline wiring (phase 2).
  - GPU/CUDA support; quantization; ONNX/torchscript export.
  - Text-to-image retrieval (`embed_texts` stays unsupported → returns None).

## Decisions

### D1: Vendor a minimal adapter; do not depend on the benchmark repo
The benchmark project is outside this repository and unpinned. GeoMemory vendors a small loader module (`embeddings/olmoearth_vision.py`) that reproduces only what is needed: backbone construction from Nano config constants + state-dict loading. Rationale: keeps GeoMemory self-contained and testable; the reference remains the source for exact layer names if upstream changes.

### D2: Lazy torch import behind a `[vision]` extra
Same pattern as `[st]`: `import torch` happens inside `_load()`, never at module import. Extra pins `torch>=2.0`; since `[st]` already pulls CPU torch in Docker, adding `[vision]` costs nothing extra in the image.

### D3: Checkpoint loading contract
`torch.load(path, map_location="cpu")` → dict of tensors; strip common wrapper keys (`state_dict`, `model`) if present; `load_state_dict(..., strict=True)` so corrupt/mismatched checkpoints fail loudly with path context wrapped in a `ModelNotLoadedError`.

### D4: Input normalization
Accept path / bytes / PIL image; convert everything to RGB PIL, resize to the model's expected tile size (per Nano config), scale to [0,1], normalize with the model's band statistics, batch to `(N, C, H, W)` numpy then single forward under `torch.inference_mode()`.

### D5: Space identifier
New id `image.olmoearth-nano-v12.v1` — distinct from the legacy `image.olmoearth.v1` used by placeholder/GGUF stubs, honoring the space-isolation invariant (different weights ⇒ different space). `ImageIndex.space_id` stays as-is for now; phase 2 aligns it when the pipeline lands.

### D6: Selection seam
Small factory function `build_vision_embedder(settings) -> VisionEmbedder` (in `services/index_service.py` or `embeddings/factory.py`): configured path + torch importable ⇒ `OlmoEarthVisionEmbedder`; otherwise `PlaceholderVisionEmbedder`. No behavior change when unconfigured.

## Risks / Trade-offs

- Upstream weight format drift (v1.2 → v1.x) breaks strict loading → mitigated by explicit error naming the checkpoint; strictness preferred over silent garbage vectors.
- Vendored loader can diverge from AllenAI updates → acceptable; pinned by thesis scope.
- torch already required by `[st]`, so no new heavy dependency risk.

## Migration Plan

Purely additive. No data migration; existing workspaces unaffected (no vision_path set ⇒ identical behavior).

## Open Questions

- Exact input resolution/band stats for v1.2 Nano: read from the benchmark's `config.yaml` during apply rather than hardcoding guesses.
