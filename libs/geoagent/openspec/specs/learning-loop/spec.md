# Learning Loop — Specification (to-be, v0.x, plumbing-only)

**Interview decision:** GeoAgent is *first an agent project*. Active Learning /
incremental-model components are deferred — their placement (inside repo as
`[ml]` extra vs separate thesis repo) is explicitly undecided. This spec fixes
only the **data plumbing contract** those components will consume later.

## Requirements

### Requirement: Feedback capture
`geo_record_feedback(rating?, comment, target_refs[])` SHALL persist expert/user corrections through GeoMemory's public feedback API (`record_feedback(FeedbackEvent)`), tagging targets (answer id, asset id, tool_run id). Raw feedback is immutable.

#### Scenario: Wrong map flagged
- **WHEN** supervisor marks a generated stress class as wrong with comment
- **THEN** event stored referencing answer id + tool_run id + artifact hashes

### Requirement: Review workflow passthrough
`geo_review_queue()` and `geo_review(example_id, accept, reviewer_id)` SHALL thin-wrap facade equivalents (`get_review_queue`, `review_example`) so human-in-the-loop labeling states stay inside GeoMemory.

#### Scenario: Accept example
- **WHEN** reviewer accepts a pending dataset example
- **THEN** state flips to accepted and it becomes export-eligible

### Requirement: Dataset export
`geo_export_dataset(task_type, output_dir)` SHALL wrap facade `export_dataset` producing JSONL for downstream training; export files register as artifacts.

#### Scenario: Training hand-off
- **WHEN** ML work starts (deferred component)
- **THEN** it consumes exported JSONL + run logs — no new coupling to agent internals

### Requirement: Run-log analytics export
`geo_export_runs(output_path, filters?)` SHALL dump ToolRun rows (tool, status, latency, budgets hit, from_cache) to CSV/JSONL for thesis metrics (Tool Execution Success Rate, response time).

#### Scenario: Thesis metric extraction
- **WHEN** scenario evaluation needs success rate per tool family
- **THEN** one export yields analyzable rows without touching agent.db directly

### Requirement: Interface stability promise
The plumbing above (feedback → review → export; run logs) is the ONLY contract
the future ML layer may rely on. Core SHALL NOT import any ML module; adding ML
later must not change these signatures.

## Non-goals (explicitly deferred)

- Uncertainty sampling; replay buffer; incremental XGBoost; scenario runner
  (A/B/C); forgetting-rate computation. Placement TBD.
