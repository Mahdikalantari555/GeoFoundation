# rsmetric Library — Specification (v0.1)

The `rsmetric` library is the monorepo-incorporated version of the upstream
`metric_et` package (GitHub: Mahdikalantari555/metric). It implements the METRIC
(Mapping Evapotranspiration with Internalized Calibration) algorithm for
estimating actual evapotranspiration (ETa) from Landsat Collection 2 Level-2
imagery at 30 m resolution.

## Requirements

### Requirement: Package identity
The top-level importable package SHALL be `rsmetric` (not `metric_et`). The
public API entry point is `from rsmetric import METRICPipeline`. Version is
`0.1.0`. Python ≥3.10.

#### Scenario: Import check
- **WHEN** `import rsmetric` runs
- **THEN** `METRICPipeline` is accessible; no `metric_et` namespace exists

### Requirement: Core classes preserved
`DataCube`, `constants`, and all pipeline-stage classes SHALL be preserved with
unchanged signatures. Scientific behavior is not altered by migration.

#### Scenario: DataCube round-trip
- **WHEN** a band is added and retrieved via `DataCube().add('ndvi', arr).get('ndvi')`
- **THEN** the returned array is identical to the input

### Requirement: CLI entry point
The `rsmetric` CLI command SHALL be registered and callable (`rsmetric --help`).
Existing click groups are preserved; command names are unchanged.

### Requirement: Test suite preserved
All existing pytest tests under `rsmetric/tests/` SHALL pass after migration.
No test logic is altered.

### Requirement: Documentation
README.md SHALL reference the monorepo path (`libs/rsmetric/`) and list only
the shipped library files. Legacy workflow docs (`WORKFLOW_USAGE.md`, etc.)
are excluded.

## Non-goals

- Porting the upstream openspec specs into this change; they remain as
  reference documentation only.
- Adding new METRIC features (no new indices, no new satellite sensors).
- Changing scientific parameter defaults.
