## Why

The thesis uses a standalone METRIC ETa implementation at `/home/asus/Projects/metric`.
It is currently a separate git repo, outside the GeoFoundation monorepo, which
means it cannot be consumed as a first-class library by GeoAgent tools and cannot
share testing / linting infrastructure. The model has no agent-facing tool, so
the research pipeline (satellite ingestion → ET mapping → stress insight) is
broken at the tool-consumption layer.

## What Changes

1. Clone `https://github.com/Mahdikalantari555/metric` into `libs/rsmetric/` inside
   the monorepo, remove its `.git` directory so it becomes a first-class monorepo
   submodule with no independent history.
2. Rename the Python package from `metric_et` to `rsmetric` (top-level importable
   as `import rsmetric`). Retain `METRICPipeline` as the public entry point.
3. Remove files that are research scaffolding but not needed as a shipped library:
   `Fetch_Data.py`, `Calculate_et.py`, `calculate_et_planetary.py`,
   `interpolate_et.py`, `run_metric_workflow.py`, `WORKFLOW_USAGE.md`,
   `scripts/`, `examples/` (keep `README.md` adapted to monorepo context).
4. Rewrite `pyproject.toml`: change `requires-python` to `>=3.10`, align
   optional extras with the monorepo convention (`[rs]` for heavy RS deps),
   update the CLI script name from `metric-et` to `rsmetric`.
5. Add `libs/rsmetric` to `libs/geomemory/pyproject.toml` as an optional extra
   `[rs-metric]` if geomemory itself wants to reference it (future-proof);
   add `rsmetric` as an optional `[rs]` extra in `libs/geoagent/pyproject.toml`.
6. Write a new geoagent tool `rs_compute_et` that wraps
   `rsmetric.METRICPipeline.run()` behind the existing tool registry, exposing
   one call per Landsat scene and returning artifact paths + summary stats.
7. Run ruff/mypy on migrated code; fix any pre-existing violations without
   changing scientific logic.

## Capabilities

### New Capabilities
- `rsmetric-library`: Clean monorepo library with renamed package, trimmed
  dead files, aligned pyproject.toml, no git history bleed.
- `geoagent-rs-tool`: `rs_compute_et` tool in the GeoAgent registry — one call
  to run the full METRIC pipeline on a Landsat scene, outputs GeoTIFFs registered
  as tool artifacts.

### Modified Capabilities
- `gis-tools` (geoagent): The existing `geo_compute_indices` tool computes NDVI/EVI
  natively; the new `rs_compute_et` tool delegates to `rsmetric` when the `[rs]`
  extra is installed. Both coexist — indices-first for simple calls, ET pipeline
  for energy-balance work.

## Impact

- **New lib**: `libs/rsmetric/` (cloned + renamed from external repo).
- **GeoAgent tool**: `rs_compute_et` in `src/geoagent/tools/rs_tools.py`;
  registered under `[rs]` extra wiring.
- **API surface**: No server/router changes — `rs_compute_et` runs client-side
  via the tool registry threadpool.
- **Deps**: `rsmetric` adds numpy/scipy/pandas/xarray/rasterio/geopandas/
  matplotlib/seaborn/cartopy/click/pyyaml/loguru/tqdm/requests. All lazy-imported
  behind `[rs]` in geoagent; no new top-level deps for base installs.
- **Risks**: Pre-existing code has minor style/mypy issues; must be fixed in the
  migration step. Scientific logic is preserved verbatim during rename.
