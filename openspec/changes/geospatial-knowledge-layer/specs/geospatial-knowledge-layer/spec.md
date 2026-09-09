## Purpose

Stores structured entities and typed relations derived from ingested documents and approved candidate memories, enabling graph-traversal queries and relation-augmented search within the workspace.

## ADDED Requirements

### Requirement: Entity store
The system SHALL persist entities in an `entity` table with fields `{id, name, kind, workspace_id, spatial_bbox, created_at}`. Entity `kind` SHALL be one of `concept`, `location`, `sensor`, `product`, `stress_type`, or `metric`. A geospatial entity SHALL carry a non-null `spatial_bbox`; a non-spatial entity SHALL have null bbox.

#### Scenario: Entity created from document extract
- **WHEN** the entity extractor identifies "NDVI" as a metric mentioned in an ingested document
- **THEN** an entity row with `kind="metric"`, `name="NDVI"`, and `evidence_id` pointing to the source segment is inserted

#### Scenario: Entity created with spatial extent
- **WHEN** the extractor identifies "Khuzestan" as a location mentioned alongside a bbox in the document
- **THEN** an entity row with `kind="location"`, `name="Khuzestan"`, and `spatial_bbox=[51,35,52,36]` is inserted

### Requirement: Relation storage
The system SHALL store typed relations in the existing `relation` table, extended so that `source_id` and `target_id` reference entity ids (not just segment ids). The `evidence_id` field continues to point to the source segment or candidate memory that justified the relation.

#### Scenario: Approved graph_relation proposal populates entities and relations
- **WHEN** a `KnowledgeChangeProposal` with `proposal_type="graph_relation"` and diff `{"original": null, "proposed": {"source": "salinity", "predicate": "causes", "target": "reduced_NDVI"}}` is approved
- **THEN** entities for "salinity" and "reduced_NDVI" are created (or linked if they already exist) and a relation row is inserted with the approved predicate

#### Scenario: Relation query by source entity
- **WHEN** `GET /api/v1/entities/{id}/relations` is called
- **THEN** the response lists all relations where the entity is either source or target, with predicate and confidence

### Requirement: Entity extraction from documents
The system SHALL run an `EntityExtractor` during document ingest (configurable, defaults to LLM-driven) and persist discovered entities linked to the ingested segment. Extraction SHALL be best-effort: failures SHALL not abort the ingest.

#### Scenario: Extractor runs silently on failure
- **WHEN** the entity extractor raises an exception during ingest
- **THEN** the segment is still persisted and the error is logged; the job completes successfully

#### Scenario: Rule-based extractor catches known patterns
- **WHEN** a document contains "NDVI < 0.2 indicates crop stress"
- **THEN** the default rule-based extractor creates a `metric` entity for "NDVI" and a `stress_type` entity for "crop stress" and a relation `NDVI --indicates--> crop_stress`

### Requirement: Relation-augmented search
The search API SHALL accept an optional `expand_relations` boolean. When true, hits whose segments link to known entities ALSO return related entities' segments as supplementary context appended after the primary ranked results.

#### Scenario: Expansion appends related context
- **WHEN** `search("salinity", expand_relations=True)` is called and segment S1 links to entity "salinity" which has a relation to entity "EC"
- **THEN** results include the primary ranked hits plus supplementary hits from segments linking to entity "EC"

#### Scenario: Expansion disabled is unchanged
- **WHEN** `search("salinity", expand_relations=False)` is called
- **THEN** results match current behavior (no supplementary context)

### Requirement: Entity traversal API
The workspace facade SHALL expose `traverse(entity_id, depth=1)` returning the entity plus its direct (or depth-N) relations with target entities. Depth is capped at 3.

#### Scenario: Depth-1 traversal
- **WHEN** `traverse(entity_id="salinity", depth=1)` is called
- **THEN** the result includes the entity, its outgoing relations, and the target entities with their kinds

#### Scenario: Depth cap enforced
- **WHEN** `traverse(entity_id="X", depth=5)` is called
- **THEN** the effective depth is capped at 3 and the response is returned without error

## MODIFIED Requirements (from evolutionary-memory spec)

### Requirement: Knowledge graph proposal integration
Candidate memories that imply entities/relations SHALL generate graph proposals. **Extended:** upon approval, the proposal approval path SHALL atomically create or link `entity` rows and insert `relation` rows, so that approved knowledge is immediately available for traversal and search expansion.

#### Scenario: Approved proposal is instantly traversable
- **WHEN** a graph_relation proposal is approved
- **THEN** a subsequent `traverse()` call on either entity in the relation returns the new edge without restart
