## Purpose
Introduce a dedicated, provider-agnostic embedding abstraction so GeoMemory consumers depend on an interface, not on `onnxruntime`/`torch` details, with `ONNXEmbeddingProvider` as the lightweight canonical implementation (Xenova/all-MiniLM-L6-v2 quantized).

## ADDED Requirements

### Requirement: EmbeddingProvider interface
The system SHALL expose `embeddings/provider.py:EmbeddingProvider` (Protocol) with `space_id: str`, `model_id: str`, `dimension: int`, `embed(texts) -> np.ndarray`, `embed_query(texts) -> np.ndarray`, `embed_batch(texts, batch_size) -> np.ndarray`. `GeoMemory`, `IndexService`, `SearchService`, and all `RetrievalBackend`s SHALL depend only on this interface for dense text embeddings.

#### Scenario: Interface isolates inference
- **WHEN** `IndexService.build_index` is inspected
- **THEN** it accepts an `EmbeddingProvider` and never imports `onnxruntime`, `torch`, or `sentence_transformers` directly

#### Scenario: Future providers are pluggable
- **WHEN** `FutureOpenAIProvider`, `FutureVoyageProvider`, or `FutureCustomProvider` are configured
- **THEN** they satisfy the same protocol and can be returned by `factory.build_text_embedder` without changing callers (stubs may raise `NotImplementedError` with an actionable hint in this change)

### Requirement: ONNXEmbeddingProvider is the canonical text provider
`ONNXEmbeddingProvider` SHALL be the default `EmbeddingProvider` when `embedding_provider` is unset or `"onnx"`. It SHALL produce `384`-dimensional `float32` L2-normalized vectors via `onnxruntime` + `tokenizers` using the quantized weights `Xenova/all-MiniLM-L6-v2` file `onnx/model_quantized.onnx` (preferred) with fallback order `onnx/model.onnx` → `model_quantized.onnx` → `model.onnx`, mean-pooling over `attention_mask`, and e5 family prefix handling. It SHALL report `space_id=text.onnx.<safe-model>.v1` (isolated per modality+model) and `dimension=384`.

#### Scenario: Quantized default loads
- **WHEN** the local snapshot for `Xenova/all-MiniLM-L6-v2` contains `onnx/model_quantized.onnx` and `tokenizer.json`
- **THEN** `ONNXEmbeddingProvider(model_name="Xenova/all-MiniLM-L6-v2").embed(["hello world"])` returns shape `(1, 384)` float32 with row norm `1.0 ± 1e-5` without importing `torch`

#### Scenario: ONNX parity gate
- **WHEN** the same 50 fixture sentences are embedded via the previous `sentence-transformers/all-MiniLM-L6-v2` reference vectors and via the new quantized ONNX provider
- **THEN** cosine correlation >0.998 and mean L2 delta <1e-3

### Requirement: No PyTorch in the default embedding path
The default install SHALL NOT import or require `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, or `safetensors` to embed text; `torch` SHALL remain reachable only via the opt-in `geomemory[vision]` extra (OLMoEarth Nano).

#### Scenario: Torch-free install
- **WHEN** `pip install geomemory` is performed in a clean environment without `[vision]`
- **THEN** `pipdeptree` and `import importlib.metadata; distributions()` contain neither `torch` nor `txtai`, and `ONNXEmbeddingProvider.embed` succeeds while `import torch` raises `ModuleNotFoundError` (or is absent)

### Requirement: Workspace settings for provider selection
`WorkspaceSettings` SHALL accept `embedding_provider: "onnx" | "openai" | "voyage" | "custom" | "hashing" | "llamacpp"` (default `"onnx"`), `onnx_model_name: str` (default `"Xenova/all-MiniLM-L6-v2"`), and preserve `st_model_name`/`embedding_backend="sentence-transformers"` only as a deprecated alias that maps to `onnx` with a migration warning and requires `reindex`.

#### Scenario: Deprecated ST alias warns
- **WHEN** a workspace with `embedding_backend="sentence-transformers"` and `st_model_name="sentence-transformers/all-MiniLM-L6-v2"` is opened after the change
- **THEN** `GeoMemory.open` emits a warning naming the new `onnx` provider and `Xenova/all-MiniLM-L6-v2`, and `search` before `rebuild_index` warns about `space_id` mismatch (`text.st.*` vs `text.onnx.*`)

### Requirement: Lazy optional imports for embeddings
Importing `geomemory` or `geomemory.embeddings` SHALL NOT import `onnxruntime`, `tokenizers`, `torch`, or `txtai`; the provider SHALL lazy-import `onnxruntime`/`tokenizers` on first `embed` and raise an actionable error naming the missing extra (`pip install geomemory[onnx]`) only when that provider is invoked without its extra installed.

#### Scenario: Lazy load
- **WHEN** `import geomemory` runs without `onnxruntime` installed and `embedding_provider="onnx"` is not yet used
- **THEN** no `ModuleNotFoundError` is raised until `embed` is called, at which point the error message instructs `pip install geomemory[onnx]`
