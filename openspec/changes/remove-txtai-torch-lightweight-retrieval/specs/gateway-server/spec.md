## Purpose
Gateway remains facade-only and its dependency graph is free of torch/txtai after the geomemory lightweight refactor.

## MODIFIED Requirements

### Requirement: HTTP facade over public libraries (deps hygiene)
The server SHALL depend only on the public facades `geomemory` / `geoagent` and its transitive graph SHALL NOT contain `txtai`, `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, or `safetensors` when installed without `[vision]`; it SHALL satisfy this via `pipdeptree` in CI.

#### Scenario: No torch in gateway env
- **WHEN** `pip install geofront-api` (or `server` deps) is performed in a clean env
- **THEN** `pipdeptree | grep -qiE "torch|txtai"` finds no matches

### Requirement: Doctor reflects lightweight stack
`GET /api/v1/doctor` diagnostics SHALL stop reporting `txtai` and SHALL report `embedding_provider` (active provider, space_id, dimension) and `sqlite_vec` (`installed`, `loadable`, `version`) alongside existing LLM/Qdrant/Vision checks.

#### Scenario: Doctor after refactor
- **WHEN** `GET /api/v1/doctor` is called with `sqlite-vec` installed
- **THEN** response contains `diagnostics.sqlite_vec.loadable == true` and `diagnostics.embedding.active_provider == "onnx"` and no `txtai` key
