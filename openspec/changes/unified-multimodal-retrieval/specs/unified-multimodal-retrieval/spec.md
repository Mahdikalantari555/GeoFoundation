## Purpose

Merges text, vision, spatial, temporal, and metadata retrieval into a single query pipeline so users can discover correlated evidence across modalities in one search or ask turn.

## ADDED Requirements

### Requirement: Modality-aware search request
`SearchRequest` SHALL accept an optional `modalities` field with values `text`, `image`, or `both`. When `both` is selected, the search orchestrator SHALL invoke all configured backends (FTS5 sparse, dense text, image) and fuse their results. When omitted, behavior SHALL be unchanged (text-only hybrid search).

#### Scenario: Text-only search unchanged
- **WHEN** `search(query, modalities=None)` is called
- **THEN** only text backends run and results match current hybrid-search behavior

#### Scenario: Image-only search
- **WHEN** `search(query, modalities="image")` is called with a configured vision embedder
- **THEN** only the image backend runs; text backends are skipped

#### Scenario: Both modalities fused
- **WHEN** `search(query, modalities="both")` is called with both text and vision indexes populated
- **THEN** text and image hits are merged via RRF and returned in a single ranked list

### Requirement: Image retrieval backend adapter
An `ImageRetrievalBackend` SHALL implement the `RetrievalBackend` protocol by wrapping `ImageIndex`, converting the text query into a vision query vector via the configured vision embedder, and returning `SearchHit` objects with `modality="image"` in metadata.

#### Scenario: Backend returns image hits
- **WHEN** `ImageRetrievalBackend.search(request)` is called with a valid query embedding
- **THEN** it returns up to `request.top_k` hits from the image index with `modality="image"` set in each hit's metadata

#### Scenario: Empty index returns empty
- **WHEN** the image index has no embeddings
- **THEN** the backend returns an empty hit list without error

### Requirement: Cross-modal RRF fusion
RRF fusion SHALL combine scores from text backends and image backends into a single ranked list. Image hits SHALL be assigned a modality-specific weight factor (default 0.7× text authoritative weight) to prevent vision results from dominating when only a few images are indexed.

#### Scenario: Authoritative text dominates when few images exist
- **WHEN** 100 text hits and 3 image hits are fused
- **THEN** text hits occupy the top positions; image hits appear below them unless their RRF score is exceptionally high

#### Scenario: Balanced fusion when both indexes are populated
- **WHEN** 50 text hits and 50 image hits are fused on a query that matches both modalities
- **THEN** the top-10 result contains hits from both modalities ranked by fused score

### Requirement: Ask endpoint passes modalities through
The `/api/v1/ask` endpoint SHALL accept an optional `modalities` parameter and pass it through to the underlying `search()` call so that grounded QA can cite both text segments and image scenes.

#### Scenario: Citing an image scene
- **WHEN** ask is called with `modalities="both"` and the retrieved context includes an image hit
- **THEN** the answer's citation list includes an entry whose locator references the image scene id

### Requirement: Search UI modality toggle
The web search page SHALL expose a modality selector (`text` / `image` / `both`) that controls the `modalities` field sent to the search API.

#### Scenario: Default is text-only
- **WHEN** the user opens the search page without changing the selector
- **THEN** the request is sent with `modalities="text"` (or omitted, preserving current behavior)

#### Scenario: Both mode switches query
- **WHEN** the user selects "both" and submits a query
- **THEN** the results list groups hits by modality badge (text vs. image) while preserving a single combined rank order

## MODIFIED Requirements (from search-retrieval spec)

### Requirement: Hybrid search
The system SHALL combine sparse (SQLite FTS5) and dense (vector backend) results using Reciprocal Rank Fusion by default; `sparse`, `dense`, and linear-fusion modes SHALL be selectable. **Extended:** when `modalities="both"`, image-backend results SHALL also participate in RRF fusion with a modality weight factor.

#### Scenario: Hybrid with image fusion
- **WHEN** `search(query, modalities="both", mode="hybrid")` is called
- **THEN** FTS5, dense text, and image hits are all fused via RRF with the image weight factor applied
