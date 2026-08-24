# Remote Sensing — As-Is Specification

Baseline extracted from current implementation (`rs/` package + spatial tables). Describes existing behavior only.

## Requirements

### Requirement: Raster scene ingestion
GeoTIFF sources SHALL yield scene metadata (sensor, band list, EPSG-constrained CRS, bbox, transform, dtype, nodata, dimensions, resolution) persisted per revision, plus optional tiles with window metadata and preview paths.

#### Scenario: Scene with tiling
- **WHEN** a raster is ingested through the pipeline
- **THEN** `raster_scene` and dependent `raster_tile` rows exist; spatial index covers the footprint

### Requirement: Spectral indices
The library SHALL compute NDVI and EVI as pure-numpy functions with shape validation, plus band mapping validation against required bands and generic `compute_index` dispatch.

#### Scenario: NDVI computation
- **WHEN** NIR and RED arrays of equal shape are provided
- **THEN** `(NIR - RED) / (NIR + RED)` returns without requiring rasterio

### Requirement: Vector layer ingestion
GeoJSON/vector sources SHALL persist geometry type (OGC-checked), CRS, feature count, and footprint, with spatial indexing.

#### Scenario: GeoJSON ingest
- **WHEN** a valid GeoJSON file is ingested
- **THEN** a `vector_layer` row exists linked to the revision

### Requirement: Spatial-temporal-sensor searchability
Ingested scenes/layers SHALL be filterable by bbox, acquisition time window, and sensor through normal search filters.

#### Scenario: Filtered search
- **WHEN** search includes spatial+temporal+sensor constraints over ingested imagery
- **THEN** only conforming raster hits return, with sensor metadata attached to hits

### Requirement: Optional dependency isolation
All rasterio/geopandas/shapely/Pillow usage SHALL remain behind lazy imports so base installs function without the `rs` extra.

#### Scenario: Missing rs extra
- **WHEN** raster ingest attempted without dependencies
- **THEN** a clear error raises rather than an import crash at package load
