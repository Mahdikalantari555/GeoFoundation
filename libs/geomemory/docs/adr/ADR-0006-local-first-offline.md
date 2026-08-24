# ADR-0006: Local-first, offline-by-default execution

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

Target users are remote-sensing researchers: sensitive unpublished data, unreliable connectivity, reproducibility requirements. Cloud APIs would break privacy guarantees and golden-test determinism.

## Decision

- Everything runs **in-process on the user's machine**: parsing, embedding, generation, indexing, storage.
- Offline mode is the **default** (`init --offline` defaults true; `NetworkDisabledError` guards network paths).
- No telemetry, no license checks, no update pings anywhere in the codebase.
- All models are local GGUF files referenced from workspace settings; heavy optional deps (`ai`, `docs`, `rs`) degrade gracefully via lazy imports.
- Determinism preserved for tests: hashing embedder fallback + fixed fixtures enable golden ingestion tests.

## Consequences

- ✅ Data never leaves the machine; reproducible environments; works air-gapped.
- ✅ Base install has 4 dependencies; capabilities grow with extras.
- ❌ Quality ceilings of small local models (embedding/generation) accepted vs. cloud SOTA.
- ❌ Users own model acquisition (downloading GGUFs); doctor command mitigates misconfiguration diagnostics.
