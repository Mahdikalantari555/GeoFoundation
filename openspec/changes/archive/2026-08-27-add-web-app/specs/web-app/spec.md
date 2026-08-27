# Delta: web-app

## ADDED Requirements

### Requirement: Full feature coverage
The app SHALL provide pages for workspace lifecycle/stats/settings/doctor,
collections, ingest (with dedup banner), search (modes + spatial/temporal/
sensor filters + bbox draw), grounded ask (citations + abstention), assets
inspect, index management, feedback review/export, eval benchmarks, agent
chat (SSE, tool-run timeline, guardrail cards), conversations, tools
catalog, playbooks, maps viewer, and farms reports.

#### Scenario: Search with all filters
- **WHEN** a user sets mode=hybrid, draws a bbox, picks a date range and
  sensor chips, and runs a query
- **THEN** results render with score breakdown and locator chips

### Requirement: Bilingual RTL
The UI SHALL support en and fa with runtime switching, `<html dir>` flip,
logical-property styling, and Intl formatting. Layout SHALL be smoke-checked
in both directions.

#### Scenario: Language switch
- **WHEN** the user switches en → fa
- **THEN** text translates and layout mirrors without broken alignment

### Requirement: Gateway-only consumption
The app SHALL call only the gateway `/api/v1` (generated client) and SHALL
NOT import or assume direct library access.

#### Scenario: Client generation
- **WHEN** the OpenAPI schema changes and the client is regenerated
- **THEN** type errors surface at build time, not runtime

### Requirement: Realtime updates
Workspace/asset/collection stats SHALL refresh via SSE invalidation without
manual reload; long jobs SHALL show progress.

#### Scenario: Ingest completes while viewing Overview
- **WHEN** an ingest job finishes and `asset_created` arrives
- **THEN** stats cards and asset lists update automatically

### Requirement: Graceful degradation
Gateway down, workspace closed, and LLM-unavailable SHALL render explicit
status states (connection pill, abstention cards with reason), never blank
screens or crashes.

#### Scenario: LLM key missing
- **WHEN** the user opens Ask with no API key configured
- **THEN** the answer renders as an abstention card with the reason
