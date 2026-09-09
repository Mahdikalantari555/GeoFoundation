## Why

GeoMemory stores documents, segments, and candidate memories as flat text, but has no structured representation of the entities and relationships those texts describe. The `relation` table exists with one row-insertion path triggered by approved proposals, but there is no entity store, no automatic extraction, and no traversal API. Researchers cannot ask "what does this workspace know about salinity?" and get a graph-structured answer — only text chunks that mention salinity. Adding a lightweight geospatial knowledge layer turns GeoMemory from a document memory into a structured knowledge engine while keeping domain logic out of the core library.

## What Changes

- Add an `entity` table alongside the existing `relation` table, with fields `{id, name, kind, workspace_id, created_at}` and a spatial_bbox column for geospatial entities.
- Add `EntityExtractor` — a pluggable extractor interface with a default LLM-driven implementation (using the configured LLM backend) and a rule-based fallback for structured patterns (e.g., "NDVI < 0.2 indicates stress").
- During ingest, run the entity extractor on document text; persisted entities are linked to the source segment via `evidence_id`.
- Approved `graph_relation` proposals from the evolutionary memory engine insert into the new `entity` + `relation` tables atomically.
- Add a `traverse(entity_id)` API on the facade that returns direct relations and transitive depth-N neighbors.
- Extend search to optionally follow relations: when `search(query, expand_relations=True)`, hits whose segments link to known entities also surface related entities' segments as supplementary context.

## Capabilities

### New Capabilities
- `geospatial-knowledge-layer`: Entity/relation storage, extraction from documents and candidate memories, traversal API, and relation-augmented search.

### Modified Capabilities
- `evolutionary-memory` (geomemory): extends the `graph_relation` proposal approval path to atomically populate both `entity` and `relation` tables.
- `search-retrieval` (geomemory): extends search to support optional relation-expansion mode.

## Impact

- **Code**: `src/geomemory/core/models.py` (+Entity model); `src/geomemory/storage/schema.sql` (+entity table); `src/geomemory/knowledge/entities.py` (new module); `src/geomemory/knowledge/extractors.py` (new module); `src/geomemory/feedback/proposals.py` (extend approval path); `src/geomemory/core/workspace.py` (+traverse, +expand_relations search).
- **APIs**: Additive — `GET /api/v1/entities/{id}`, `GET /api/v1/entities/{id}/relations`, `POST /api/v1/search` gains `expand_relations` flag.
- **Deps**: No new hard deps; LLM-driven extraction uses the existing `LLMBackend` protocol. Rule-based extractor is pure Python.
- **Risks**: Entity extraction quality depends on LLM performance; rule-based fallback covers common RS patterns. Traversal depth capped at 3 to prevent explosion.
