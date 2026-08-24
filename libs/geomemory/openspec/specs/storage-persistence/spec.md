# Storage & Persistence — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Requirements

### Requirement: Single-file database
All structured state SHALL live in one SQLite database per workspace, opened in WAL mode with foreign keys enforced.

#### Scenario: Connect
- **WHEN** `connect(db_path)` runs
- **THEN** WAL and `foreign_keys=ON` are active and schema is ensured

### Requirement: Versioned migrations
Schema changes SHALL be applied through a version-registry (`schema_migration` table) with idempotent application.

#### Scenario: Fresh database
- **WHEN** initialize runs on an empty DB
- **THEN** schema v1 is created and version recorded

### Requirement: Sparse index integrity
FTS5 (`segments_fts`) SHALL mirror the `segment` table via triggers so text search never diverges from stored segments.

#### Scenario: Insert segment
- **WHEN** a segment row is inserted/updated/deleted
- **THEN** the FTS index reflects it without manual sync

### Requirement: Spatial index
Spatial bboxes SHALL be queryable through an RTree virtual table keyed by a mapping table that preserves TEXT entity ids.

#### Scenario: Bbox lookup
- **WHEN** spatial entities are persisted and queried by bbox
- **THEN** matching entity ids return via the RTree + mapping join

### Requirement: Content-addressed object store
Raw bytes SHALL be stored once under their SHA-256 hash at `objects/<aa>/<bb>/<hash>`, immutable; the store exposes put/get/exists/delete/size and total counts.

#### Scenario: Put bytes
- **WHEN** bytes are stored
- **THEN** returned hash equals content SHA-256 and re-storing is a no-op dedupe

### Requirement: Typed repositories
Domain tables SHALL be accessed through typed repositories with parameterized SQL (no string interpolation).

#### Scenario: Repository round-trip
- **WHEN** models are written and read back through repositories
- **THEN** field fidelity holds (ids, JSON metadata, timestamps)
