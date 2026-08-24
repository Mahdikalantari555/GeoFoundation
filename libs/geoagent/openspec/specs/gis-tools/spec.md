# GIS Tools — Specification (to-be, v0.1)

Native rasterio/geopandas/shapely/matplotlib wrappers (interview decision:
native-first; no MCP client in v0.x). All lazy-imported behind the `[rs]`
extra; all are deterministic (`cacheable=true`) and artifact-producing.

## Requirements

### Requirement: Optional dependency isolation
All GIS deps SHALL import lazily inside functions; missing `[rs]` extra yields a structured error naming the extra — never an import-time crash.

#### Scenario: Base install
- **WHEN** `geo_reclassify` runs without rasterio installed
- **THEN** error says "install geoagent[rs]" and nothing else breaks

### Requirement: geo_compute_indices
`geo_compute_indices(input_tif, indices[], output_dir)` SHALL compute requested spectral indices and write one single-band GeoTIFF per index (CRS/nodata preserved) plus a stats summary (min/max/mean/p05/p95 via `band_statistics`). v0.x supports:
- `NDVI`, `EVI` via `geomemory.rs.raster.spectral` (public-ish pure-numpy functions);
- `NDWI`, `SAVI` as local pure-numpy formulas (GeoMemory implements only NDVI/EVI today — gap documented upstream).

Band mapping SHALL be validated (e.g. Sentinel-2 defaults `{"blue":2,"green":3,"red":4,"nir":8}` overridable).

#### Scenario: NDVI map
- **WHEN** a 4-band Sentinel-2 crop is processed with `["NDVI"]`
- **THEN** `ndvi_<input>.tif` exists, stats return, ToolRun records both artifacts

### Requirement: geo_reclassify
`geo_reclassify(input_tif, rules[{min,max,out}], output_tif)` SHALL map value ranges to integer classes, preserve georeferencing and nodata, and reject overlapping ranges at validation.

#### Scenario: Stress classes
- **WHEN** NDVI tif reclassified with rules `[[-1,0.4,2],[0.4,0.6,1],[0.6,1,0]]`
- **THEN** output contains only {0,1,2} + nodata, transform/CRS unchanged

### Requirement: geo_polygonize
`geo_polygonize(input_tif, output_geojson, band=1, value_field="class", simplify_tolerance?)` SHALL convert class raster → polygons (`rasterio.features.shapes`), write GeoJSON with class attributes, optionally simplify geometries in CRS units.

#### Scenario: Vector stress map
- **WHEN** reclassified stress raster is polygonized
- **THEN** GeoJSON polygons carry `class ∈ {0,1,2}` and open in any GIS tool

### Requirement: geo_symbology
`geo_symbology(input_geojson, field, classification{scheme,classes}, palette, out_png)` SHALL render a static classified choropleth (matplotlib, no server): scheme ∈ `quantiles|equal_interval|manual`, palette named or hex list. Returns PNG artifact plus class-break table (LLM-readable insight summary).

#### Scenario: Insight figure
- **WHEN** stress polygons symbolized by `class` with manual breaks
- **THEN** PNG legend matches breaks; summary lists area share per class

### Requirement: geo_zonal_stats
`geo_zonal_stats(raster_tif, polygons_geojson, out_csv)` SHALL compute per-polygon mean/min/max/std/count (+nodata share) and write CSV; returns compact top-level aggregates (area-weighted mean, worst-class share) for the LLM.

#### Scenario: Farm report numbers
- **WHEN** farm polygons zonal-stats against NDVI tif
- **THEN** CSV row per farm_id; summary names lowest-mean farms first

### Requirement: Artifact discipline
Every file output SHALL be registered as an artifact (path + sha256) in its ToolRun; tools return paths + compact summaries only — never raw arrays in LLM context.

## Non-goals

- Reprojection/resampling tools (add on demand); web map tiles; interactive maps;
  GEE script execution (separate CLI-runner concern).
