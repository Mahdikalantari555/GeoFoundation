# CLI Runner — Specification (to-be, v0.1)

Config-driven wrapper that turns any external CLI into a registry tool —
primary case: the researcher's own stress-analysis library
(`python -m <lib> --start-date ... --end-date ... --bbox ...`), so the agent
executes it in one shot instead of re-deriving invocation each turn.

## Requirements

### Requirement: Declarative tool registration
External CLIs SHALL be declared in `agent.yaml` under `cli_tools:`: `name`, `description`, `params` JSON-Schema, `argv_template` (list with `{param}` placeholders), `cwd`, `timeout_s`, `outputs` ({artifacts_glob, parse: json|text|none}). Registry loads them at startup as first-class tools.

#### Scenario: Stress lib as tool
- **WHEN** `run_stress_analysis` is declared with argv template `["python","-m","stresslib","--bbox","{bbox}","--start","{start_date}","--end","{end_date}"]`
- **THEN** the LLM sees a typed tool with date/bbox params and can call it directly

### Requirement: Safe expansion and execution
Placeholders SHALL substitute only validated, schema-conforming values; argv stays a list (never shell string interpolation). Execution uses fixed `cwd`, bounded env passthrough, enforced timeout.

#### Scenario: Injection attempt
- **WHEN** a param value contains shell metacharacters
- **THEN** they reach the subprocess as literal argument bytes — no shell interpretation

### Requirement: Dry-run
Every runner tool supports `dry_run=true`: returns expanded argv + resolved artifact paths without executing, so user or LLM can verify before spending compute.

#### Scenario: Verify before run
- **WHEN** dry_run requested for a 6-week time series job
- **THEN** exact command prints; nothing executes; no cache entry writes

### Requirement: Output capture
Runner SHALL capture stdout/stderr (tails bounded), exit code; on non-zero exit returns structured failure with stderr tail. Declared artifacts are glob-resolved post-run, hashed, registered in the ToolRun; `parse=json` attaches parsed JSON (bounded) to the result.

#### Scenario: Library crash
- **WHEN** stress lib exits 1 with traceback on stderr
- **THEN** ToolRun status=failed, error tail ≤ 2000 chars, LLM sees last lines only

### Requirement: Cacheable by input hash
Runner tools default `cacheable=true`; key includes sha256 of every input file referenced by params plus normalized args.

#### Scenario: Same farm, same dates
- **WHEN** identical analysis re-requested next session
- **THEN** cached artifacts return instantly with `from_cache: true`

### Requirement: Playbook hand-off
On first successful run of a runner tool with fully specified params, the agent MAY offer "save as playbook"; the resulting playbook references this tool name and param pattern (see playbooks spec).

## Non-goals

- Auto-discovery of arbitrary CLIs from code reading; installing dependencies
  of external libs; GEE authentication flows (user preconfigures).
