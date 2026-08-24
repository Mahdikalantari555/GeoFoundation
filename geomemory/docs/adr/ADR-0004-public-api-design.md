# ADR-0004: Public API Design — facade + Pydantic models + protocol backends

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

Consumers are heterogeneous: CLI scripts, Streamlit pages, notebooks, future agents. The library needs one stable entry surface while internals evolve quickly (alpha stage). The Streamlit reference app is contractually restricted to public API only.

## Decision

1. **Facade**: everything routes through `GeoMemory.open(path)` / `.create(path, config)` (`core/workspace.py`). Facade methods return domain objects, never DB rows.
2. **Pydantic v2 everywhere**: all domain objects inherit `GeoMemoryModel` (strict types, JSON-safe dumps). Public exports limited to `geomemory/__init__.py`: facade + 17 models + 8 exceptions rooted at `GeoMemoryError`.
3. **Protocol-based extensibility**: `TextEmbedder`, `VisionEmbedder`, `RetrievalBackend`, `LLMBackend` protocols let implementations vary (hashing vs llama-cpp embedders; numpy/txtai/vector backends; Null vs llama.cpp LLM).
4. **Registries** (`LoaderRegistry`, `ChunkerRegistry`, …) allow adding loaders/chunkers without touching the pipeline dispatch.
5. **In-process event bus** (`DomainEvent`, e.g. `asset.created`) as an extension seam.
6. CLI mirrors the facade 1:1 (`geomemory ingest|search|ask|index|eval|feedback|inspect|doctor|init|app`) with lazy imports so startup stays light.

## Consequences

- ✅ Dashboard/notebook code stays readable and stable; internal refactors invisible to consumers.
- ✅ Strict typing end-to-end enforced by mypy `--strict` on `src/`.
- ✅ New modalities (e.g., tables, more sensors) slot in via loaders/chunkers/models without API breaks.
- ❌ Facade grew into an 1152-LOC god-object mixing orchestration + SQL (documented debt; extraction pending).
- ❌ No async API surface; everything synchronous.
