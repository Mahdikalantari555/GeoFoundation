# Workspace Management — As-Is Specification

Baseline extracted from the current implementation (`main` @ `364b897`, v0.1.0). Describes existing behavior only; no proposed changes.

## Purpose

A workspace is a directory holding all GeoMemory state: settings file, SQLite database, content-addressed object store, and vector indexes. This capability covers creation, opening, configuration, collections, and diagnostics.

## Requirements

### Requirement: Workspace creation
The system SHALL create a workspace directory containing `workspace.yaml`, `geomemory.db` (initialized to schema v1), and `objects/`.

#### Scenario: Create new workspace
- **WHEN** `GeoMemory.create(path, config)` is called on a non-existent or empty directory
- **THEN** the directory is initialized with settings, schema-v1 database, and object store
- **AND** a default workspace row exists in the `workspace` table

#### Scenario: Refuse to clobber
- **WHEN** creation targets an existing valid workspace
- **THEN** the system raises instead of reinitializing

### Requirement: Workspace open
The system SHALL open an existing workspace and expose settings.

#### Scenario: Open existing
- **WHEN** `GeoMemory.open(path)` is called on a valid workspace
- **THEN** subsequent operations (ingest/search/ask) operate against that state

#### Scenario: Missing workspace
- **WHEN** the path has no `.geomemory` marker/database
- **THEN** `WorkspaceNotFoundError` is raised

### Requirement: Settings persistence
Workspace settings (name, offline flag, model paths, language) SHALL persist in `workspace.yaml` and be readable/updatable through the facade.

#### Scenario: Update setting
- **WHEN** `update_settings(**changes)` is called
- **THEN** the YAML file reflects the change on disk and in memory

### Requirement: Collections
Workspaces contain named collections; assets belong to exactly one collection.

#### Scenario: Collection lifecycle
- **WHEN** a collection is created, listed, fetched, or archived via the facade
- **THEN** state persists in the `collection` table with workspace scoping

### Requirement: Diagnostics
The system SHALL provide environment and workspace health checks.

#### Scenario: Doctor run
- **WHEN** `geomemory doctor -w PATH` executes
- **THEN** optional dependency presence, database integrity, and settings sanity are reported without mutating data
