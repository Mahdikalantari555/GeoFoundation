# docker-deployment Spec

## Purpose

Reproducible container images and a compose stack so a full GeoMemory stack (app + Qdrant) starts with one command, with persistent volumes for workspace data and model caches.

## ADDED Requirements

### Requirement: Two image targets

The repository SHALL provide a Docker build producing two targets from one Dockerfile: a CLI target containing the installed package plus AI/vector extras, and a UI target that additionally serves the Streamlit reference app.

#### Scenario: CLI image builds and runs
- **WHEN** the CLI target is built and run with `--help`
- **THEN** the `geomemory` CLI help text is printed and the container exits zero

#### Scenario: UI image serves the app
- **WHEN** the UI target is run with the documented port mapping
- **THEN** the Streamlit app responds on the mapped port inside the container's network

### Requirement: One-command compose stack

The repository SHALL provide a compose file that starts Qdrant and the geomemory UI together, pre-configured so the app connects to Qdrant by service name, without manual environment editing.

#### Scenario: Stack comes up wired
- **WHEN** `docker compose up` is run from the repository root
- **THEN** a Qdrant service and the geomemory UI start, the UI's workspace settings point at the Qdrant service hostname, and health checks report both services healthy

### Requirement: Persistent volumes

Compose SHALL define named volumes for the Qdrant storage, the geomemory workspace directory, and the Hugging Face model cache, so restarting or rebuilding containers does not lose indexed data or re-download models.

#### Scenario: Data survives recreation
- **WHEN** an index is built against the running stack, the containers are removed, and the stack is started again
- **THEN** previously indexed records remain searchable without re-ingestion and the embedding model is not re-downloaded

### Requirement: Configuration via environment

Container behavior SHALL be configurable through documented environment variables (Qdrant URL, model name, workspace path) with sensible defaults matching the compose topology.

#### Scenario: Override Qdrant endpoint
- **WHEN** the UI container is started with an alternate Qdrant URL environment variable
- **THEN** the application uses that endpoint instead of the compose default
