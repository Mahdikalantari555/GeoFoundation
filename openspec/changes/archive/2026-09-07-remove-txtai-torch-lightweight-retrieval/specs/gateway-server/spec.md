## Purpose
Gateway remains facade-only and its dependency graph is free of torch/txtai after the geomemory lightweight refactor.

## MODIFIED Requirements

### Requirement: HTTP facade over public libraries
The server SHALL expose `/api/v1` endpoints that call only the public facades of `geomemory` and `geoagent`, and SHALL NOT import any library internal module, and its transitive graph SHALL NOT contain `txtai`, `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, or `safetensors` when installed without `[vision]`; it SHALL satisfy this via `pipdeptree` in CI.

#### Scenario: Facade-only imports
- **WHEN** the server package is inspected for imports
- **THEN** every `geomemory`/`geoagent` import resolves to a public API path

#### Scenario: No torch in gateway env
- **WHEN** `pip install geofront-api` (or `server` deps) is performed in a clean env
- **THEN** `pipdeptree | grep -qiE "torch|txtai"` finds no matches

## ADDED Requirements

### Requirement: Doctor reflects lightweight stack
`GET /api/v1/doctor` diagnostics SHALL stop reporting `txtai` and SHALL report `embedding_provider` (active provider, space_id, dimension) and `sqlite_vec` (`installed`, `loadable`, `version`) alongside existing LLM/Qdrant/Vision checks.

#### Scenario: Doctor after refactor
- **WHEN** `GET /api/v1/doctor` is called with `sqlite-vec` installed
- **THEN** response contains `diagnostics.sqlite_vec.loadable == true` and `diagnostics.embedding.active_provider == "onnx"` and no `txtai` key
