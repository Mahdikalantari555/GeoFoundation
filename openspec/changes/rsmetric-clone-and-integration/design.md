# Design: rsmetric clone-and-integration

## Library layout after migration

```
libs/rsmetric/
  pyproject.toml           # renamed pkg, >=3.10, [rs] extras
  README.md                # adapted to monorepo context
  rsmetric/                # formerly metric_et/
    __init__.py            # re-exports from old metric_et/__init__.py
    core/                  # DataCube, constants (unchanged logic)
    io/                    # LandsatReader, MeteoReader, fetchers
    pipeline/              # METRICPipeline
    calibration/           # DTCalibration, anchor_pixels
    surface/               # albedo, vegetation, emissivity, indices
    radiation/             # shortwave, longwave, net_radiation
    energy_balance/        # soil, sensible, latent heat flux
    et/                    # instantaneous, daily, quality
    preprocess/            # cloud_mask, resampling
    output/                # writer, product_organizer, visualization
    validation/            # integration, comprehensive
    weather/               # fetch
    utils/                 # exceptions, logger
    cli/                   # interface.py (click CLI)
    tests/                 # pytest suite (preserved)
  openspec/                # existing openspec specs from upstream (read-only ref)
```

## Rename strategy

- Package dir: `metric_et/` → `rsmetric/`
- Top-level `__init__.py` exports updated: `from rsmetric.core ...`, etc.
- Internal cross-module imports updated: `metric_et.X` → `rsmetric.X` throughout.
- External references (test fixtures, README examples) updated in place.

## Files removed (research scaffolding, not library code)

| File | Reason |
|---|---|
| `Fetch_Data.py` | Standalone script, replaced by `io.PlanetaryComputerFetcher` |
| `Calculate_et.py` | Duplicate of `pipeline.METRICPipeline` usage pattern |
| `calculate_et_planetary.py` | Same — legacy runner |
| `interpolate_et.py` | Ad-hoc interpolation, no unit tests, not part of spec |
| `run_metric_workflow.py` | Legacy wrapper around Pipeline |
| `WORKFLOW_USAGE.md` | User guide for standalone usage, superseded by docstrings |
| `scripts/` | CI/dev scripts, not shipped with package |
| `examples/` | Keep as a future addition if needed; exclude from initial migration |
| `uv.lock` | Lockfile not needed; use conda env + pip editable install |

## pyproject.toml changes

```toml
[project]
name = "rsmetric"
version = "0.1.0"
description = "METRIC ETa model — remote sensing evapotranspiration from Landsat"
requires-python = ">=3.10"           # align with GeoFoundation
license = {text = "MIT"}

[project.optional-dependencies]
rs = [
  "numpy>=1.24", "scipy>=1.10", "pandas>=2.0", "xarray>=2023.1",
  "rasterio>=1.3", "rioxarray>=0.14", "geopandas>=0.14",
  "matplotlib>=3.7", "seaborn>=0.12", "cartopy>=0.22",
  "click>=8.1", "pyyaml>=6.0", "loguru>=0.7", "tqdm>=4.65",
  "requests>=2.28",
]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[project.scripts]
rsmetric = "rsmetric.cli.interface:cli"
```

## GeoAgent tool contract

`rs_compute_et` tool definition:

```python
ToolDefinition(
    name="rs_compute_et",
    description=(
        "Run the full METRIC ETa pipeline on a Landsat Collection 2 Level-2 "
        "scene directory. Requires [rs] extra. Writes ET_daily.tif, ETrF.tif, "
        "LE.tif, H.tif, Rn.tif, G.tif, dT.tif to output_dir."
    ),
    params={
        "type": "object",
        "properties": {
            "landsat_dir": {"type": "string", "description": "Path to Landsat scene dir"},
            "output_dir": {"type": "string"},
            "config": {"type": "object", "description": "Optional METRIC config override"},
        },
        "required": ["landsat_dir", "output_dir"],
    },
    timeout_s=600.0,
    cacheable=False,   # ET computation is not deterministic across scenes
)
```

Returns: `{"artifacts": [...], "stats": {"ET_daily_mean": float, "ETrF_mean": float}}`

## Execution flow

```
GeoAgent → rs_compute_et(args)
          → rsmetric.METRICPipeline(config=config).run(landsat_dir, meteo_data, output_dir)
          → registers each output tif as ArtifactRef(path, sha256)
          → returns compact summary
```
