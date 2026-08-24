# Tool Registry — Specification (to-be, v0.1)

Single source of truth for what the agent can do.

## Requirements

### Requirement: Tool definition model
A tool SHALL be a Pydantic `ToolDefinition`: unique snake_case `name` (family-prefixed: `geo_*`), `description` (LLM-facing), JSON-Schema `params`, `returns` summary, `timeout_s` (default 60), `cacheable` flag, optional `extras` (required install extras). Definitions live in Python (`@tool` decorator) — YAML registration is a later add-on, not v0.x.

#### Scenario: Duplicate name
- **WHEN** two tools register with the same name
- **THEN** registry raises at startup, naming both modules

### Requirement: Manifest for prompts
Registry SHALL render a compact tool manifest (name + description + params schema) for the system prompt, with a token-budget cap; overflow tools are summarized by family and loadable on demand via a `list_tools(family)` tool.

#### Scenario: Many tools
- **WHEN** registered tools exceed the manifest token budget
- **THEN** least-recently-used families collapse to one-line summaries

### Requirement: Argument validation
Every call SHALL validate arguments against the tool's JSON Schema **before** execution. Invalid args return a structured error as the tool result for the LLM to correct — never an uncaught crash of the loop.

#### Scenario: Wrong bbox order
- **WHEN** bbox arrives as `[n,e,s,w]`
- **THEN** validation error states expected `[w,s,e,n]`

### Requirement: Audited execution
Each execution SHALL persist a ToolRun in `agent.db`: id, conversation/turn refs, tool name, args JSON + sha256, status (`ok|validation_error|failed|timeout|budget_refused`), latency_ms, error tail (bounded), artifact list (path + sha256). No execution without an audit row.

#### Scenario: Timeout
- **WHEN** a tool exceeds its timeout
- **THEN** status=`timeout`, partial side effects are reported if the tool supports cancellation, and the LLM receives a recovery hint

### Requirement: Deterministic caching
Tools with `cacheable=true` SHALL cache results under `<workspace>/runs/cache/<args_hash>/`; key = sha256(tool name + normalized args + sha256 of each input file). Cache hit returns stored artifacts + `from_cache: true`.

#### Scenario: Recompute avoidance
- **WHEN** identical reclassify runs twice on identical input
- **THEN** second run returns cached GeoJSON path without touching rasterio

### Requirement: Path sandbox
Path-valued parameters SHALL resolve only within configured sandbox roots (`agent.yaml` `sandbox.roots`, default: workspace dir). Absolute paths outside roots and symlink escapes SHALL be rejected with validation errors.

#### Scenario: Escape attempt
- **WHEN** input_path = `/etc/passwd`
- **THEN** validation error names the allowed roots

### Requirement: Budget enforcement hook
The registry SHALL accept per-turn budgets from agent-core (max calls, wall clock) and refuse excess executions with `status=budget_refused`, so budget policy has exactly one implementation point.

## Non-goals

- Subprocess isolation per call (in-process v0.x); remote tool execution;
  dynamic tool creation by the LLM.
