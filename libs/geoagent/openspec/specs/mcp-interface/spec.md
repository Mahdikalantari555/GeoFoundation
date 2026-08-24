# MCP Interface — Specification (to-be, phase P5)

Expose the tool registry as an MCP server so external agents/clients can drive
GeoAgent capabilities. Interview decision: **client-side MCP stays out of scope**
until this phase; native tools carry v0.x.

## Requirements

### Requirement: Stdio MCP server
`geoagent mcp` SHALL serve the registry over stdio MCP: `tools/list` maps to registry manifest; `tools/call` routes through the same validation → sandbox → audit path as internal calls (single execution path invariant).

#### Scenario: External client call
- **WHEN** an MCP client calls `geo_zonal_stats`
- **THEN** ToolRun row is written identically to an internal call

### Requirement: Exposure allowlist
`agent.yaml` `mcp.expose[]` SHALL allowlist exposed tools (default: none). Sessions/conversations are NOT exposed — server calls are stateless.

#### Scenario: Private tool stays private
- **WHEN** allowlist omits `geo_record_feedback`
- **THEN** client's tools/list never shows it and call attempts are refused

## Non-goals

- MCP client integration (attaching external servers like gis-mcp) — revisit
  after P5 if needed; network transports (HTTP/SSE); auth (local trust model).
