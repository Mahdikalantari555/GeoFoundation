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

### Requirement: LLM provider settings
`WorkspaceSettings` SHALL accept additive, backward-compatible LLM configuration fields:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `llm_provider` | `null \| "llamacpp" \| "api"` | `null` | Backend selection; `null` preserves baseline behavior |
| `llm_api_base_url` | `str \| null` | Kilo gateway URL | OpenAI-compatible chat-completions endpoint |
| `llm_api_key_env` | `str` | `"GEOMEMORY_LLM_API_KEY"` | Name of env var holding the secret |
| `llm_model_id` | `str \| null` | `"kilo-auto/free"` | Model id sent to the gateway |
| `llm_context_window` | `int` | `32768` | Context window for llama.cpp and QA budgeting (values up to 200000 valid) |

Absent fields SHALL NOT change existing workspace behavior.

#### Scenario: Settings round-trip
- **WHEN** a workspace is created with only legacy fields and later updated with `llm_provider: api`
- **THEN** the settings file round-trips without data loss for either generation of fields

### Requirement: Secrets stay out of persisted settings
API keys SHALL never be written to `workspace.yaml` or any persisted store; they SHALL be read at use time from the environment variable named by `llm_api_key_env`.

#### Scenario: Key not persisted
- **WHEN** a user configures the api provider and runs ask/doctor
- **THEN** no key material appears in `workspace.yaml`, logs, or database rows

### Requirement: Diagnostics report LLM resolution
`geomemory doctor` SHALL report the resolved LLM backend: provider, model id, whether the API key env var is set, and context window.

#### Scenario: Doctor output
- **WHEN** doctor runs in a workspace with `llm_provider: api`
- **THEN** output names the provider, model id, key presence (never the key value), and configured context window
