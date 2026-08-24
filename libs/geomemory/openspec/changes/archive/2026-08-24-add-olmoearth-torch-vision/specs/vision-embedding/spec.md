# vision-embedding Spec

## Purpose

Image embedding via OLMoEarth v1.2 Nano loaded directly from native PyTorch weights, behind the existing vision-embedder contract — enabling offline satellite-imagery similarity search without llama.cpp or GGUF conversion, while keeping the core package installable without torch.

## ADDED Requirements

### Requirement: Native-torch model loading

When a vision model path is configured and the `torch` extra is installed, the system SHALL load the OLMoEarth v1.2 Nano checkpoint directly as a PyTorch state dict (CPU) and produce embeddings from the model's forward pass; it SHALL NOT require llama.cpp, GGUF conversion, a JVM, or network access.

#### Scenario: Checkpoint loads on CPU
- **WHEN** the configured path points to a valid OLMoEarth Nano `.pth` file and images are embedded
- **THEN** the state dict is loaded with CPU mapping and embeddings are produced without any llama.cpp dependency being imported

### Requirement: Embedding output contract

The embedder SHALL accept image inputs (filesystem paths, raw bytes, or PIL images), SHALL return an `(N, D)` float32 array with each vector L2-normalized, and SHALL report its own stable embedding-space identifier distinct from text spaces.

#### Scenario: Batch embed shape and normalization
- **WHEN** three image inputs are embedded
- **THEN** the result is a `(3, D)` float32 array whose row norms are each 1.0 within tolerance

#### Scenario: Space isolation
- **WHEN** the embedder reports its space identifier
- **THEN** it begins with the image modality prefix and differs from every text embedder space identifier

### Requirement: Configuration via settings and environment

The system SHALL select the torch-based embedder when `vision_path` is set in workspace settings or the `GEOMEMORY_VISION_PATH` environment variable is present; when neither is set, existing behavior (no vision embedder; operations raise an actionable error) SHALL be unchanged.

#### Scenario: Path configured selects real embedder
- **WHEN** a workspace is opened with `vision_path` pointing at the Nano weights and the embedder factory is invoked
- **THEN** a torch-native OLMoEarth embedder bound to that path is returned rather than the placeholder

#### Scenario: No configuration unchanged
- **WHEN** no vision path is configured
- **THEN** no torch model is loaded at open time and image-embedding attempts raise an error explaining how to configure one

### Requirement: Graceful degradation without dependencies

When the `torch` extra is not installed and the torch-based backend is selected, every vision-embedding operation SHALL fail with an actionable error naming the missing extra (`pip install geomemory[vision]`) instead of crashing at import time.

#### Scenario: Extra missing
- **WHEN** `vision_path` is configured in an environment without torch and an image embed is requested
- **THEN** the operation raises an error instructing installation of the `[vision]` extra

### Requirement: Corrupt or missing checkpoint fails loudly

When the configured checkpoint file does not exist or cannot be deserialized as a state dict, embedding operations SHALL fail with a clear error identifying the file path.

#### Scenario: Missing file
- **WHEN** `vision_path` points to a nonexistent file and an embed is requested
- **THEN** the error names the missing path

#### Scenario: Invalid content
- **WHEN** the file exists but contains non-state-dict data
- **THEN** loading fails with an error identifying the invalid checkpoint rather than producing garbage vectors

### Requirement: Doctor visibility for vision

The system health report SHALL report whether `torch` is importable and whether the configured vision-model path exists on disk.

#### Scenario: Doctor reports vision state
- **WHEN** `geomemory doctor` runs in a workspace with a vision path configured
- **THEN** the report states torch availability and whether the checkpoint file was found
