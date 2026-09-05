# Customizable Plugins — Specification

Dynamic, user-described tool creation for GeoAgent. Any user can extend the agent by describing a capability in natural language; the system scaffolds a typed tool, validates and sandboxes it, and registers it alongside static tools — without touching core. Customizability grows with use: every described tool refines the plugin seam.

## Requirements

### Requirement: Three plugin seams
The registry SHALL support three additive seams, all discovered via the same `register(registry)` contract and isolated per plugin:
1. `workspace/plugins/*.py` — drop-in Python files;
2. `entry_points` group `geoagent.tools` — installed packages;
3. **user-described plugins** — generated from natural language.
A broken plugin (any seam) SHALL be reported and skipped without blocking startup or other plugins.

#### Scenario: Drop-in still works
- **WHEN** `<workspace>/plugins/my_tool.py` exposes `register(registry)` and is valid
- **THEN** `load_plugins` registers it and lists `plugin:my_tool` as loaded

#### Scenario: Bad plugin isolated
- **WHEN** a user-described plugin fails validation or raises during `register`
- **THEN** it is marked `failed` with reason, startup continues, and other plugins remain usable

### Requirement: Describe-to-tool flow
A user SHALL be able to create a tool by describing it: `describe_tool(description, name_hint?, params_hint?, returns_hint?)`. The system SHALL propose a `ToolDefinition` (snake_case `name` with `geo_` family prefix when applicable, LLM-facing `description`, JSON-Schema `params`, `returns`, `timeout_s`, `cacheable`) plus a Python implementation skeleton, then validate, sandbox-check, and stage it for approval. No tool is registered until explicitly confirmed (or auto-confirmed per policy).

#### Scenario: Natural language becomes tool
- **WHEN** user says "make a tool that computes NDVI from two GeoTIFF bands and returns a reclassified GeoTIFF"
- **THEN** the system proposes `name=geo_ndvi_reclassify`, JSON-Schema with `red_path, nir_path, out_path, threshold`, and a sandboxed implementation using `rasterio`, awaiting confirmation

#### Scenario: Duplicate name rejected
- **WHEN** a described name collides with an existing tool
- **THEN** validation returns `duplicate tool name 'geo_xxx' (already registered by y)` and suggests an alternative

### Requirement: Generated implementation contract
Generated code SHALL be a single-file module exposing `register(registry)` that registers exactly one `ToolDefinition` + `ToolFn` with signature `(args: dict, ctx: RunContext) -> Any | ToolResult`. It SHALL use only allowed imports (stdlib + declared extras), respect path sandboxing, and declare artifacts via `ToolResult.artifacts`. The harness SHALL reject code that imports disallowed modules, accesses network, or escapes `sandbox.roots`.

#### Scenario: Sandbox violation rejected
- **WHEN** generated code tries `open("/etc/passwd")` or `requests.get(...)`
- **THEN** static analysis/validation fails with `path outside sandbox roots` or `disallowed import: requests`

#### Scenario: Artifact declared
- **WHEN** the tool writes `runs/custom/ndvi.tif`
- **THEN** it returns `ToolResult(artifacts=[ArtifactRef(path=..., sha256=...)])` so the audit and cache layers see it

### Requirement: Validation and audit reuse
Every user-described tool SHALL pass the same gates as static tools: JSON-Schema arg validation before execution, path sandbox enforcement, budget enforcement, timeout, deterministic cache (when `cacheable=true`), and audited `ToolRun` persistence (`tool, args, args_hash, status, latency_ms, error, artifacts, from_cache`). Validation errors return structured results for the LLM to repair, never a harness crash.

#### Scenario: Invalid args are recoverable
- **WHEN** LLM calls `geo_ndvi_reclassify` with `threshold="high"` instead of number
- **THEN** result status=`validation_error` with `expected number at $.threshold`, and the LLM can retry

#### Scenario: Audited run
- **WHEN** a custom tool executes
- **THEN** `agent.db` contains a `ToolRun` row indistinguishable from a built-in tool run

### Requirement: Lifecycle — draft → active → versioned
User tools SHALL have lifecycle `draft (staged) → active → disabled | superseded`. `draft` is not callable until approved. `active` tools are callable and appear in the manifest/OpenAI tools. Updates create a new version that `supersedes` the prior file (kept for audit/revert). Disable/rollback SHALL be reversible.

#### Scenario: Approve activates
- **WHEN** user confirms a staged draft
- **THEN** its file is written to `<workspace>/plugins/<name>.py`, loaded via `load_plugin_module`, and `Registry.names()` includes it

#### Scenario: Iterative refinement along the way
- **WHEN** user says "add a `colormap` param to `geo_ndvi_reclassify`"
- **THEN** the system generates a v2 draft that supersedes v1, diff is shown, and on approval v2 becomes active while v1 is archived

### Requirement: Customizability grows with use
The plugin seam SHALL be increasingly customizable: per-tool `extras`, `timeout_s`, `cacheable`, `sandbox` overrides; per-workspace `plugins.yaml` for defaults; and composition (custom tool may call other tools via `ctx.store`/`Registry` or declare `depends_on`). The manifest SHALL surface custom tools with the same token-budget handling as built-ins (overflow families collapse).

#### Scenario: Composed tool
- **WHEN** a custom tool is described as "zonal stats over the NDVI output"
- **THEN** its implementation may call `Registry.call("geo_zonal_stats", ...)` within its budget, and the budget hook counts it as one of the turn's tool calls

#### Scenario: Manifest includes custom tools
- **WHEN** many custom tools exist and token budget is exceeded
- **THEN** their family (e.g., `geo_custom`) collapses like built-ins and is expandable via `list_tools(family)`

### Requirement: Persistence and portability
Custom plugins SHALL be persisted as plain `*.py` files under `<workspace>/plugins/` (or `<workspace>/agent/plugins/` when configured) plus an optional `plugins.yaml` manifest, so copying the workspace copies its tools. Exported workspaces SHALL not auto-execute untrusted plugins on import without explicit opt-in.

#### Scenario: Workspace copy carries tools
- **WHEN** a workspace directory is copied to another machine
- **THEN** its custom `*.py` plugins travel with it and load on next `load_plugins` call

### Requirement: Security and governance
User-described plugin creation SHALL require an explicit capability flag (`plugins.allow_dynamic=true` in `agent.yaml`, default `false` in enterprise profiles). Generated code SHALL be shown as a diff with source, proposed `ToolDefinition`, and required extras before activation. All promotions, disables, and rollbacks SHALL be audited with author/timestamp.

#### Scenario: Enterprise gate
- **WHEN** `allow_dynamic=false`
- **THEN** `describe_tool` returns `status=refused` with hint "enable plugins.allow_dynamic in agent.yaml"

#### Scenario: Diff review
- **WHEN** a draft is staged
- **THEN** the caller receives `{name, description, params schema, code_diff, sandbox_roots, required_extras}` for human approval
