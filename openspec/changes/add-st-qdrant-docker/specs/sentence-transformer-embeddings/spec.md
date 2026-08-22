# sentence-transformer-embeddings Spec

## Purpose

Text embedding via sentence-transformers models behind the existing text-embedder contract, enabling high-quality multilingual (en/fa) semantic embeddings without GGUF/llama-cpp, while keeping the core package installable without torch.

## ADDED Requirements

### Requirement: Optional-dependency embedding backend

When the sentence-transformers extra is installed and the workspace settings select it, the system SHALL produce dense text embeddings using the configured sentence-transformers model; when the extra is not installed and this backend is selected, every embedding operation SHALL fail with an actionable error naming the missing extra.

#### Scenario: Backend selected and installed
- **WHEN** workspace settings set the embedding backend to `sentence-transformers` with model `intfloat/multilingual-e5-small` and a batch of texts is embedded
- **THEN** an `(N, 384)` float32 array is returned for that model, and each output vector is L2-normalized

#### Scenario: Backend selected but extra missing
- **WHEN** the sentence-transformers package is not installed and this backend is selected
- **THEN** embedding fails with an error message instructing installation of the extra (e.g. `pip install geomemory[st]`)

### Requirement: e5 input prefixing

The system SHALL transparently apply the e5-family input prefixes — `query: ` for search queries and `passage: ` for indexed documents — so callers never construct prefixed strings themselves.

#### Scenario: Query vs passage vectors differ
- **WHEN** the same short string is embedded once through the query path and once through the passage path
- **THEN** the two output vectors are different (prefixes applied), and both remain valid 384-dimensional vectors

### Requirement: Embedding-space isolation

Each configured sentence-transformers model SHALL map to exactly one stable embedding space identifier derived from the model name, and vectors from different spaces SHALL never be compared or stored together.

#### Scenario: Space identifier stability
- **WHEN** two embedder instances are created for the same model name in the same session
- **THEN** both report the identical space identifier, and it differs from the space identifiers of the hashing and llama-cpp embedders

#### Scenario: Model change forces new space
- **WHEN** the configured model name changes between builds
- **THEN** the resulting space identifier changes, and previously built indexes for the old space are never reused for the new one

### Requirement: Doctor visibility

The system health report SHALL report whether the sentence-transformers package is importable, alongside the existing optional dependencies.

#### Scenario: Doctor reports new optional dependency
- **WHEN** `geomemory doctor` runs in an environment without sentence-transformers installed
- **THEN** the optional-dependency section lists sentence-transformers as not installed without crashing
