# Memory Tools — Specification (to-be, v0.1)

Wrap the GeoMemory public facade. GeoAgent is a *consumer*: it imports nothing
deeper than `import geomemory` root exports and never opens GeoMemory's SQLite
directly.

## Requirements

### Requirement: Workspace binding
All memory tools operate on one workspace path from `agent.yaml` (`memory.workspace`). Missing workspace SHALL produce a setup-hint error (`GeoMemory.create` vs `open`).

#### Scenario: Unbound workspace
- **WHEN** any memory tool runs before `memory.workspace` is set
- **THEN** error explains how to point to an existing workspace or create one

### Requirement: geo_ingest
`geo_ingest(source_path, collection)` SHALL wrap `GeoMemory.ingest`, creating the collection by name when absent (idempotent). It SHALL surface dedup short-circuits as first-class results (`skipped: duplicate hash`) rather than errors. Supported inputs follow GeoMemory kinds: document/code/table/raster/vector.

#### Scenario: Re-ingest same PDF
- **WHEN** the same file is ingested twice
- **THEN** second call reports `skipped=true, reason=duplicate hash` with existing asset id

#### Scenario: GeoTIFF ingest
- **WHEN** a `.tif` is ingested
- **THEN** result includes scene metadata (sensor/bbox/date when present) usable by later spatial filters

### Requirement: geo_search (retrieval workhorse)
`geo_search(query, top_k=5, collections?, bbox?, date_range?, sensors?)` SHALL wrap `GeoMemory.search(mode="hybrid")`, mapping `bbox=[w,s,e,n]` → `SpatialFilter` and `date_range=[start,end]` → `TemporalFilter`. Hits SHALL be trimmed for LLM consumption (per-hit char cap, locators + metadata kept). Raw `SearchResult` fields (latency, retrieval_run_id) SHALL be preserved in the ToolRun record.

**Design decision (interview):** there is NO `geo_ask` tool in v0.x. Grounded
generation is the agent's job: retrieve via `geo_search` → pack context → one
LLM call with `[S#]` citation keys → abstain when hits are empty/weak. GeoMemory
needs no LLM configuration.

#### Scenario: Spatial-temporal filtered search
- **WHEN** `geo_search("canopy stress", bbox=[48.2,31.0,48.9,31.6], date_range=["2025-07-01","2025-07-31"])`
- **THEN** only conforming segments/scenes return and each hit carries locator + metadata

#### Scenario: Empty evidence
- **WHEN** no hits return
- **THEN** the tool reports zero hits (the agent will abstain, per agent-core spec)

### Requirement: Introspection tools
`geo_list_collections`, `geo_create_collection(name, description)`, `geo_inspect(asset_id)`, `geo_stats` SHALL thin-wrap facade equivalents (`list_collections`, `create_collection`, `inspect`, `stats`), returning compact JSON.

#### Scenario: Asset provenance check
- **WHEN** `geo_inspect(asset_id)` runs on an ingested report
- **THEN** revision hash, segments, scenes/layers lists are visible

### Requirement: Citation contract for generation
When the agent generates grounded answers, every claim span SHALL carry a `[S#]` key mapped to a `geo_search` hit (segment id + locator); unmapped keys SHALL be dropped and claims without any key SHALL be flagged in the answer metadata. This contract lives here because hits originate from these tools.

#### Scenario: Fabricated citation
- **WHEN** the LLM emits `[S9]` with only S1–S3 provided
- **THEN** `[S9]` is stripped and the answer metadata records `invalid_citation_keys`

## Non-goals

- Writing to GeoMemory DB directly; bypassing facade semantics;
  multimodal/vision QA (GeoMemory experimental image index untouched).
