# sentence-transformer-embeddings Spec

## Purpose

Text embedding via sentence-transformers models behind the existing text-embedder contract, enabling high-quality multilingual (en/fa) semantic embeddings without GGUF/llama-cpp, while keeping the core package installable without torch.

## Requirements

### Requirement: Optional-dependency embedding backend

When the sentence-transformers extra is installed and the workspace settings select it, the system SHALL produce dense text embeddings using the configured sentence-transformers model; when the extra is not installed and this backend is selected, every embedding operation SHALL fail with an actionable error naming the missing extra.

#### Scenario: Backend selected and installed
- **WHEN** workspace settings set the embedding backend to `sentence-transformers` with the default model `sentence-transformers/all-MiniLM-L6-v2` and a batch of texts is embedded
- **THEN** an `(N, 384)` float32 array is returned for that model, and each output vector is L2-normalized

#### Scenario: Alternative multilingual models
- **WHEN** `st_model_name` is set to an opt-in alternative such as `intfloat/multilingual-e5-base` or `BAAI/bge-m3`
- **THEN** the embedder loads that model and reports its own distinct space identifier

#### Scenario: Backend selected but extra missing
- **WHEN** the sentence-transformers package is not installed and this backend is selected
- **THEN** embedding fails with an error message instructing installation of the extra (e.g. `pip install geomemory[st]`)

### Requirement: Model-family input prefixing

The system SHALL apply input prefixes only for model families that require them (e5 family: `query: ` for search queries, `passage: ` for indexed documents); models without prefix requirements (e.g. all-MiniLM-L6-v2) SHALL be passed through unmodified.

#### Scenario: Query vs passage vectors differ (e5)
- **WHEN** the same short string is embedded once through the query path and once through the passage path under an e5 model
- **THEN** the two output vectors are different (prefixes applied), and both remain valid vectors

#### Scenario: MiniLM passthrough
- **WHEN** texts are embedded under `all-MiniLM-L6-v2`
- **THEN** no prefix is added, so identical inputs yield identical vectors on both query and passage paths

### Requirement: Embedding-space isolation

Each configured sentence-transformers model SHALL map to exactly one stable embedding space identifier derived from the model name, and vectors from different spaces SHALL never be compared or stored together.

#### Scenario: Space identifier stability
- **WHEN** two embedder instances are created for the same model name in the same session
- **THEN** both report the identical space identifier, and it differs from the space identifiers of the hashing and llama-cpp embedders

#### Scenario: Model change forces new space
- **WHEN** the configured model name changes between builds
- **THEN** the resulting space identifier changes, and previously built indexes for the old space are never reused for the new one

### Requirement: Embedding model metadata on indexes

Every dense index build SHALL record the embedding model metadata — model name/id, vector dimension, space identifier, build timestamp — in the build manifest so any consumer can determine which model produced an index without re-deriving it.

#### Scenario: Manifest records model
- **WHEN** a dense index is built with `all-MiniLM-L6-v2`
- **THEN** the persisted manifest contains the model id, dimension (384), and space identifier

### Requirement: Model mismatch detection before search

Before executing a semantic search, the system SHALL compare the query embedder's space/model identity against the target index's recorded metadata; on mismatch it SHALL warn the user naming both models, and SHALL NOT silently mix vectors across models.

#### Scenario: Mismatch warning
- **WHEN** a workspace indexed with e5 is searched after settings switch to `all-MiniLM-L6-v2` without rebuilding
- **THEN** search emits a warning naming both models before returning results

### Requirement: Reindex on embedding model change

Changing the configured embedding model SHALL require a full rebuild of affected indexes; partial or incremental reuse of embeddings from a different model SHALL NOT occur.

#### Scenario: Rebuild clears staleness
- **WHEN** the user switches models and runs rebuild for a space
- **THEN** all vectors in that space come from the newly configured model and no stale vectors remain

### Requirement: Doctor visibility

The system health report SHALL report whether the sentence-transformers package is importable, alongside the existing optional dependencies.

#### Scenario: Doctor reports new optional dependency
- **WHEN** `geomemory doctor` runs in an environment without sentence-transformers installed
- **THEN** the optional-dependency section lists sentence-transformers as not installed without crashing
