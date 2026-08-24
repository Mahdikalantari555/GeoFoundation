# Advisor Tools — Specification (to-be, phase P3)

Farm-facing decision-support tools behind the supervisor's chat: stress
reports and irrigation/fertilization/spraying guidance. Everything grounded —
numbers from GIS tools, agronomy rules via `geo_search`, citations mandatory.

## Requirements

### Requirement: Farm registry convention
Farms live as a GeoJSON asset in a designated collection (default name
`farms`); each feature carries `farm_id`, `crop`, optional `area_ha`. No
separate farm database in v0.x — the registry IS a GeoMemory asset.

#### Scenario: Unknown farm
- **WHEN** tools receive a `farm_id` absent from the farms layer
- **THEN** structured error lists available ids

### Requirement: geo_farm_report
`geo_farm_report(farm_id|bbox, start_date, end_date, indices?)` SHALL orchestrate:
1. locate farm geometry (farms layer or bbox);
2. ensure index rasters exist for the window (`geo_compute_indices`, cache-aware);
3. zonal stats per date (`geo_zonal_stats`);
4. retrieve physiological thresholds via `geo_search` (cited);
5. emit artifacts: `report.md`, `map.png`, `stats.csv`;
6. ingest `report.md` back into a `reports` collection (traceability loop).

#### Scenario: Monthly report
- **WHEN** report requested for farm 12 over July
- **THEN** three artifacts exist, report cites thresholds `[S#]`, report asset inspectable in GeoMemory

### Requirement: geo_recommend
`geo_recommend(farm_id, topic ∈ {irrigation,fertilization,spraying}, context?)` SHALL combine latest stress state (zonal stats + reclassified classes) with retrieved expert rules, returning advice whose every normative claim carries `[S#]` keys; insufficient data → abstain naming the gap.

#### Scenario: Missing stress data
- **WHEN** no raster exists for the requested window
- **THEN** abstention states what's missing and offers ingest/compute next steps

### Requirement: Supervisor chat surface (P3)
A minimal Streamlit page SHALL reuse agent sessions (same `agent.db`) providing chat + artifact links + map preview. No separate auth system v0.x (local trust).

#### Scenario: Same history everywhere
- **WHEN** supervisor continues a conversation started in CLI
- **THEN** turns and tool-run links are identical

## Non-goals

- Multi-tenant web deployment; notification/scheduling; sensor/IoT ingestion;
  automatic prescription without human confirmation.
