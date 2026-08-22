# Architecture Decision Records

ADRs record significant architectural decisions **found in the codebase** (extracted from the current implementation, not proposed changes).

| # | Title | Status |
|---|---|---|
| [ADR-0001](ADR-0001-vector-search-selection.md) | Vector Search: embedded libraries over a dedicated vector DB | Accepted |
| [ADR-0002](ADR-0002-embedding-model-strategy.md) | Embedding Model Strategy: GGUF via llama-cpp + hashing fallback | Accepted |
| [ADR-0003](ADR-0003-storage-architecture.md) | Storage Architecture: single SQLite + content-addressed object store | Accepted |
| [ADR-0004](ADR-0004-public-api-design.md) | Public API Design: facade + Pydantic models + protocol backends | Accepted |
| [ADR-0005](ADR-0005-hybrid-retrieval-fusion.md) | Hybrid Retrieval with Reciprocal Rank Fusion | Accepted |
| [ADR-0006](ADR-0006-local-first-offline.md) | Local-first, offline-by-default execution | Accepted |
| [ADR-0007](ADR-0007-grounded-qa-provenance.md) | Grounded QA with citations and abstention | Accepted |

Format: lightweight MADR-style (Context / Decision / Consequences).
