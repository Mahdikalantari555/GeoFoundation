## Context

The `relation` table already exists in schema with basic columns. The `Relation` model exists but is only used by `ProposalEngine` for a single hard-coded insert path. No `entity` table exists. No extractor module exists. The gap is structural: entities are implicit (mentioned in text) but never stored as first-class records.

## Goals / Non-Goals

**Goals:**
- Add `entity` table and `Entity` model.
- Add `EntityExtractor` protocol with an LLM-driven default and a rule-based fallback.
- Wire extraction into the ingest pipeline (best-effort, non-blocking).
- Extend proposal approval to atomically populate entity + relation tables.
- Add `traverse()` and `expand_relations` search mode.

**Non-Goals:**
- Full graph-database capabilities (no Cypher, no Gephi export).
- Entity resolution / deduplication across similar names (e.g., "NDVI" vs "normalized difference vegetation index") — deferred; each mention creates a separate entity with a `variant_of` metadata link possibility.
- Real-time graph visualization in the dashboard — UI rendering is out of scope.
- Domain-specific ontology enforcement — the layer is intentionally schema-flexible.

## Decisions

### D1. Entity extracted from text via LLM prompt, not fine-tuned model
The default extractor uses the workspace's configured LLM backend with a structured-output prompt asking it to return JSON entities and relations found in the segment text. This keeps the dependency on existing infra and avoids adding a new model. A rule-based fallback (`RuleBasedExtractor`) handles common RS patterns without LLM calls, ensuring extraction works offline.

Alternative considered: spaCy or another NER library. Rejected because it adds a hard dependency and doesn't understand RS-domain terms without custom training.

### D2. Entities linked to segments via evidence_id, not copied
Entities are not redundant copies of text — they are pointers. The `evidence_id` on an entity points to the segment that first mentioned it. This preserves the provenance chain and means entities can be queried independently of their source documents.

### D3. Relation-augmented search appends, does not re-rank
When `expand_relations=True`, supplementary hits from related entities are appended after the primary RRF-ranked results rather than mixed in. This preserves the quality of the primary ranking while adding related context. Users who want fused reranking can run a separate traversal query.

## Risks / Trade-offs

- [LLM extraction cost] → Every document ingest triggers an LLM call for entity extraction. Mitigation: extractors run in a threadpool (existing pattern); rule-based extractor handles short segments without LLM; LLM extractor skipped when `offline=true`.
- [Entity name collisions] → Two segments may mention "NDVI" and create two entity rows with the same name. Deduplication is deferred; metadata can carry `canonical_name` for future use.
- [Traversal explosion] → Depth-3 traversal on a dense graph could return thousands of hits. Mitigation: cap total expanded hits at 50; log warning if cap reached.

## Migration Plan

New `entity` table added via schema migration v2. Existing `relation` rows keep their current `source_id`/`target_id` semantics (segment ids) until proposals begin populating entity ids. A one-time backfill script can migrate high-confidence existing relations if needed.

## Open Questions

- Should entity `kind` be a closed enum (as proposed) or free-form? Recommendation: closed enum for now; extendable later.
- Should the rule-based extractor be domain-configurable (user-provided pattern list) or fixed? Recommendation: fixed set of common RS patterns for v1; config file for v2.
