# ADR-0001: Vector Search — embedded libraries over a dedicated vector DB

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

GeoMemory needs dense nearest-neighbor search over segment embeddings. Candidate approaches: dedicated vector database (Qdrant, Milvus, pgvector), managed cloud service, or embedded library in-process. Constraints from project spec: local-first, CPU-capable, zero external services, single-user research tool.

## Decision

Use **embedded, in-process vector search** with a backend abstraction (`index/backend.py` `RetrievalBackend` protocol) and two concrete implementations:

1. `NumpyBackend` — pure-numpy cosine similarity over term-frequency vectors; dependency-free fallback.
2. `TxtaiBackend` — txtai embeddings index (optional `ai` extra).
3. `VectorBackend` — persisted numpy-based dense store with save/load + `IndexManifest`.

No network vector DB anywhere; indexes persist as files under the workspace (`indexes/<space>/`), described by JSON manifests (`index/manifest.py`).

## Consequences

- ✅ Zero infrastructure; workspace dir is fully portable; offline guaranteed.
- ✅ Backends are swappable per space id; embedding spaces stay isolated.
- ❌ Brute-force numpy scan is O(n) — acceptable at 10³–10⁴ segments, not beyond (see gap analysis / roadmap v0.2+ ANN decision).
- ❌ txtai is an optional heavy dep; code must gracefully degrade to hashing/numpy paths when absent.
