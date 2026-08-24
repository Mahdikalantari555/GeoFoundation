# Tasks: add-olmoearth-torch-vision

## 1. Config seam

- [x] 1.1 Add `GEOMEMORY_VISION_PATH` → `vision_path` to the env-override map in `src/geomemory/core/config.py`; unit test that the env var overrides a loaded workspace.yaml
- [x] 1.2 Add `[vision]` extra (`torch>=2.0`) to `pyproject.toml`

## 2. Torch-native embedder

- [x] 2.1 Create `src/geomemory/embeddings/olmoearth_vision.py`: lazy torch import; `_load()` builds the Nano backbone, applies `torch.load(map_location="cpu")`, unwraps wrapper keys, `load_state_dict(strict=True)` with path-naming errors; export from `embeddings/__init__.py`
- [x] 2.2 Implement input pipeline: path/bytes/PIL → RGB PIL → resize to Nano tile size → normalize with band stats → `(N, C, H, W)` float32 batch
- [x] 2.3 Implement `embed_images` (forward under `torch.inference_mode()`, L2-normalized float32 output, space_id `image.olmoearth-nano-v12.v1`) and `embed_texts` returning `None`
- [x] 2.4 Unit tests with stubbed torch module + tiny fake state dict: load success, embed shape/dtype/L2 norm, missing-extra error names `[vision]`, missing file error names path, corrupt checkpoint error

## 3. Selection & doctor wiring

- [x] 3.1 Add `build_vision_embedder(settings)` factory: configured path ⇒ OlmoEarthVisionEmbedder, else PlaceholderVisionEmbedder; unit test both branches
- [x] 3.2 Add `doctor_vision(settings)`: report torch importability and checkpoint-file existence; extend doctor aggregation and its unit tests

## 4. Quality gates

- [x] 4.1 `ruff check` clean across new modules and tests
- [x] 4.2 `mypy --strict` passes on all touched files
- [x] 4.3 Full `pytest` suite green in conda env `ai`; no test requires GPU, network, or the real weights file
- [x] 4.4 `openspec validate add-olmoearth-torch-vision --strict` passes before apply/archive
