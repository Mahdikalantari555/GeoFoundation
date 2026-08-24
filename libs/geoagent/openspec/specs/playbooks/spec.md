# Playbooks — Specification (to-be, v0.1)

Saved, versioned tool sequences so repeated workflows run fast without the LLM
re-planning or re-reading anything. SKILL.md-inspired format.

## Requirements

### Requirement: Playbook file format
A playbook is `<workspace>/playbooks/<name>.md`: YAML frontmatter (`name`, `version`, `triggers[]` fa/en phrases, `params` JSON-Schema, `tools_used[]`) followed by markdown steps; each step = `{tool, args}` where args may reference `{{params.x}}` and `{{steps.n.result.<field>}}`.

#### Scenario: Stress-map playbook
- **WHEN** `farm-stress-map.md` declares steps `[geo_compute_indices → geo_reclassify → geo_polygonize → geo_symbology]`
- **THEN** one user phrase ("نقشه تنش مزرعه X از تاریخ A تا B") executes all four via the registry

### Requirement: Compact prompt presence
The system prompt SHALL list only playbook names + triggers (+ params schema on request); full bodies load at execution time. Token cost per turn stays constant as playbooks grow.

#### Scenario: Fifty playbooks
- **WHEN** workspace holds 50 playbooks
- **THEN** prompt carries 50 trigger lines, not 50 step lists

### Requirement: Fast-path execution
When a playbook matches and all params resolve without gaps, execution SHALL bypass planning LLM calls entirely — steps go straight through registry validation/audit. Missing params → normal agent loop asks/fills them, then resumes fast path.

#### Scenario: Fully-specified replay
- **WHEN** user supplies farm bbox + dates matching a playbook
- **THEN** zero intermediate LLM calls occur between steps

### Requirement: Save from transcript
Command `/playbook save [name]` SHALL have the LLM draft a playbook from the conversation's successful tool sequence (args templated), show it for confirmation, then write the file with `version: 1`. Hand-edits allowed; content hash tracks versions.

#### Scenario: Capture expert flow
- **WHEN** researcher finishes a novel multi-tool run and saves it
- **THEN** next identical intent replays deterministically from the file

### Requirement: Failure semantics
Step failures inside a playbook SHALL stop execution with per-step status report (which step, which args, which error) — no silent partial artifacts; completed-step artifacts remain listed for resume decisions.

#### Scenario: Mid-chain failure
- **WHEN** polygonize fails after indices+reclassify succeeded
- **THEN** report shows steps 1–2 ok with artifact paths, step 3 failed with reason

## Non-goals

- Cross-workflow DAG engine; conditional branching beyond param templates;
  sharing playbooks over network.
