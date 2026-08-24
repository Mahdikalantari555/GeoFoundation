# Delta: workspace-management

## ADDED Requirements

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
