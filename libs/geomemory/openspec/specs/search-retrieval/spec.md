# Search & Retrieval — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Requirements

### Requirement: Hybrid search
The system SHALL combine sparse (SQLite FTS5) and dense (vector backend) results using Reciprocal Rank Fusion by default; `sparse`, `dense`, and linear-fusion modes SHALL be selectable.

#### Scenario: Hybrid query
- **WHEN** `search(query)` runs with both backends configured
- **THEN** hits from both engines are fused via RRF, deduplicated, diversity-capped (max 3 per document), and truncated to top_n

### Requirement: Query parsing
The query parser SHALL clean the query, extract inline filter expressions into `SearchFilters`, and detect intent recorded in the query plan.

#### Scenario: Filter extraction
- **WHEN** a query contains recognizable spatial/temporal/sensor hints
- **THEN** the returned plan documents parsed filters alongside raw text

### Requirement: Metadata filters
Search SHALL post-filter fused results by spatial bbox intersection, temporal window on a chosen field, sensor list, and collection scope.

#### Scenario: Spatial filter
- **WHEN** a `SpatialFilter(bbox=...)` is supplied
- **THEN** only hits whose geometry/bbox intersects survive

#### Scenario: Temporal + sensor
- **WHEN** temporal range and sensor list are supplied for raster content
- **THEN** only scenes acquired in-range from listed sensors survive

### Requirement: Retrieval auditability
Every executed search SHALL persist a `RetrievalRun` containing query, plan, filters, config, latency, and results/candidates JSON.

#### Scenario: Replayable run
- **WHEN** any search completes
- **THEN** its row enables later inspection of exactly what was retrieved and how long it took

### Requirement: Index lifecycle
The system SHALL build/rebuild vector indexes per embedding space id, persisting vectors plus a manifest (space id, model id, dimension, checksums), and SHALL keep modality spaces isolated.

#### Scenario: Rebuild
- **WHEN** `rebuild_index(space_id)` is invoked
- **THEN** the index is reconstructed from database segments with a fresh manifest
