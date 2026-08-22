# qdrant-vector-backend Spec

## Purpose

Server-mode Qdrant as a pluggable dense-retrieval backend behind the existing retrieval-backend contract, selected by workspace configuration, with one collection per embedding space so space isolation is preserved.

## ADDED Requirements

### Requirement: Config-selected vector backend

When workspace settings select Qdrant as the vector backend, dense indexing and search SHALL be served by the configured Qdrant server; when the default backend is selected or no settings are present, existing on-disk behavior SHALL be unchanged.

#### Scenario: Default unchanged
- **WHEN** a workspace has no vector-backend setting (or it equals the default) and a dense index is built and searched
- **THEN** results come from the existing local on-disk index and no network connection to Qdrant is attempted

#### Scenario: Qdrant selected
- **WHEN** the vector backend is set to `qdrant` with a server URL and segments are indexed
- **THEN** the vectors are stored in the configured Qdrant server and dense search returns ranked hits sourced from it

### Requirement: Collection per embedding space

Each embedding space SHALL map to exactly one Qdrant collection named after the space identifier; records from different spaces SHALL never share a collection.

#### Scenario: Two spaces stay separate
- **WHEN** indexes are built for two different embedding spaces against the same Qdrant server
- **THEN** two distinct collections exist and searching one never returns records from the other

### Requirement: Backend contract parity

The Qdrant backend SHALL support the full retrieval-backend contract: upsert (insert or replace by record id), search (ranked by cosine similarity of the provided query embedding, honoring `top_k`), delete by id, count, and rebuild-from-source-of-truth.

#### Scenario: Upsert is idempotent
- **WHEN** the same record id is upserted twice with different text
- **THEN** the collection contains one point for that id and search returns the latest text

#### Scenario: Delete removes hits
- **WHEN** a record is deleted by id after being indexed
- **THEN** subsequent searches never return that id and the reported count decreases

#### Scenario: Search honors top_k
- **WHEN** a search request with `top_k = 5` is executed against an index holding 100 records
- **THEN** at most 5 hits are returned, ordered by descending similarity score

### Requirement: Unreachable server fails loudly

When the configured Qdrant server is unreachable, indexing and search operations SHALL fail with a clear connection error rather than silently falling back to another backend.

#### Scenario: Server down during search
- **WHEN** the vector backend is `qdrant` and the server URL is unreachable at search time
- **THEN** the search fails with an error identifying the Qdrant connection, and no results are fabricated from local files

### Requirement: Doctor visibility

The system health report SHALL report whether the Qdrant client package is installed and, when a URL is configured, whether the server answers a connectivity check.

#### Scenario: Doctor reports Qdrant state
- **WHEN** `geomemory doctor` runs in a workspace configured for Qdrant
- **THEN** the report states the client-package availability and the server reachability result
