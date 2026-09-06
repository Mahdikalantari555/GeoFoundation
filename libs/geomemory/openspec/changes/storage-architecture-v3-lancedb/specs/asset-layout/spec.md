## Purpose
Introduce logical asset directory layout over the existing content-addressed ObjectStore.

## ADDED Requirements

### Requirement: AssetLayout abstraction
The system SHALL provide `AssetLayout` mapping logical asset paths to content-addressed physical paths:
- `assets/documents/<sha256_prefix>/<sha256>` → `objects/sha256/ab/cd/<sha256>`
- `assets/imagery/<sha256_prefix>/<sha256>` → same content-addressed target
- `assets/vectors/...`, `assets/datasets/...`

#### Scenario: Logical path resolution
- **WHEN** an asset with hash `abc123` is stored under `assets/documents/`
- **THEN** `layout.resolve("abc123", kind="document")` returns `objects/sha256/ab/c3/abc123`.

### Requirement: Workspace integration
`Workspace` SHALL initialize `AssetLayout` on creation/open. Ingest stores new assets via layout; `Asset.path` stores the logical path.

#### Scenario: Ingest via layout
- **WHEN** a document is ingested
- **THEN** bytes are written to `ObjectStore`; `Asset.path` is `assets/documents/<prefix>/<hash>`; no raw file paths in DB.
