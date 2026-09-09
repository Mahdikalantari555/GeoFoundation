## Purpose

Ensures that whenever a GeoTIFF is ingested into a workspace with `vision_path` configured, the OLMoEarth vision embedder is invoked automatically and the resulting embedding is persisted in the image index so visual-similarity search is available without a separate build step.

## ADDED Requirements

### Requirement: Automatic vision embed on raster ingest
When a GeoTIFF source is ingested and `settings.vision_path` points to a valid OLMoEarth checkpoint and the `[vision]` extra is installed, the ingestion pipeline SHALL invoke the vision embedder on the generated tile previews (or the full scene when tiles are not produced) and persist the resulting embedding in the image index under space `image.olmoearth-nano-v12.v1`.

#### Scenario: Embed produced on ingest with vision configured
- **WHEN** a GeoTIFF is ingested into a workspace where `vision_path` is set and torch is available
- **THEN** an embedding record exists in the image index keyed by the scene or tile id after ingest completes

#### Scenario: Embed skipped when vision not configured
- **WHEN** a GeoTIFF is ingested into a workspace where `vision_path` is None
- **THEN** no vision embedding is produced and the ingest completes successfully (unchanged behavior)

#### Scenario: Embed skipped when torch unavailable
- **WHEN** a GeoTIFF is ingested and the `[vision]` extra is not installed
- **THEN** ingest completes without error and no vision embedding is produced; a doctor warning notes the missing extra

### Requirement: Image-search endpoint returns embedded scenes
The search API SHALL accept a visual-similarity query mode that searches the image index by a provided query vector or by text-to-image embedding (when supported). Results are returned alongside or separately from text results depending on the selected mode.

#### Scenario: Image-similarity search by vector
- **WHEN** `search(query_vector=..., mode="image", top_k=5)` is called
- **THEN** the result contains image hits ranked by cosine similarity from the OLMoEarth index

#### Scenario: Empty index returns empty results
- **WHEN** image-similarity search is called but no embeddings have been built
- **THEN** the result contains zero hits and latency is under 10 ms
