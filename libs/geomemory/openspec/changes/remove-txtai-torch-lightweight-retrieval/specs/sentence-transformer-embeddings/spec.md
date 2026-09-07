## Purpose
Retire the sentence-transformers torch backend; its contract is superseded by `embedding-provider` (ONNX canonical). Archive this spec.

## REMOVED Requirements

### Requirement: Optional-dependency embedding backend
The requirement that the system produce dense text embeddings via `sentence-transformers` when that extra is installed is REMOVED. Dense text embeddings are now provided by `ONNXEmbeddingProvider` via `onnxruntime`.

#### Scenario: ST backend no longer exists
- **WHEN** code is inspected for `embeddings/sentence_transformer.py` or `SentenceTransformerEmbedder`
- **THEN** the file/class is absent and `pip install geomemory[st]` is no longer a valid install path (install hint suggests `pip install geomemory[onnx]`)

### Requirement: Alternative multilingual models via sentence-transformers
The scenario for alternative multilingual models (`intfloat/multilingual-e5-base`, `BAAI/bge-m3`) via `sentence-transformers` is REMOVED. Alternative models are now selected via `onnx_model_name` (`Xenova/*`, `onnx-community/*`) under the `EmbeddingProvider` abstraction.

### Requirement: Model-family input prefixing (ST)
The e5 prefix handling previously documented under `sentence-transformers` is now owned by `EmbeddingProvider / ONNXEmbeddingProvider` and remains verified there; the ST-specific scenarios are REMOVED.

### Requirement: Embedding-space isolation (ST)
The `text.st.*` space isolation requirement is REMOVED (superseded by `text.onnx.*` under `embedding-provider`). A legacy `text.st.*` manifest now triggers `ReindexRequired` rather than being a valid space.

### Requirement: Embedding model metadata on indexes (ST)
The ST model-manifest requirement is REMOVED (superseded by `embedding-provider` manifest with `dimension=384`, `space_id=text.onnx.*.v1`).

### Requirement: Model mismatch detection before search (ST)
The ST mismatch warning requirement is REMOVED (superseded by `embedding-provider` mismatch warning between `text.st.*` legacy and `text.onnx.*` current).

### Requirement: Reindex on embedding model change (ST)
The ST reindex requirement is REMOVED (superseded by `storage-architecture` reindex utility for provider/model change).

### Requirement: Doctor visibility for sentence-transformers
The requirement that Doctor list `sentence-transformers` as an optional dependency is REMOVED; Doctor now reports `sqlite-vec` and `embedding_provider` (`onnx`) instead.

