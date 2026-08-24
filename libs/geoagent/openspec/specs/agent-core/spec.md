# Agent Core — Specification (to-be, v0.1)

The reasoning loop: LLM + tool calling + planning + session state.

## Requirements

### Requirement: OpenAI-compatible LLM backend
Agent core SHALL depend on an `LLMBackend` protocol (`chat(messages, tools, **opts) -> ChatResult`). The default implementation SHALL target the OpenAI Chat Completions API shape (`base_url`, `api_key`, `model`, `temperature`, `timeout`), configurable via `agent.yaml` and standard env vars (`OPENAI_API_KEY`, `OPENAI_BASE_URL`) so any compatible provider works by config change alone.

**Out of scope for v0.x:** local runtimes (llama.cpp/GGUF). The protocol seam is reserved; no local implementation ships.

#### Scenario: Provider switch
- **WHEN** `agent.yaml` changes `base_url`/`model` to another OpenAI-compatible provider
- **THEN** no code changes are needed; tool-calling behavior is unchanged

#### Scenario: Missing credentials
- **WHEN** a chat turn starts with no API key configured
- **THEN** a clear setup error returns (which var/file to set), not a stack trace

### Requirement: Tool-calling loop with budget
The loop SHALL use native function calling (OpenAI `tools` format) and SHALL enforce per-turn budgets: max tool calls (default 8), max wall-clock seconds (default 120), max LLM iterations (default 6). Exceeding a budget SHALL end the turn with partial results plus reason.

#### Scenario: Runaway plan
- **WHEN** the LLM requests more tool calls than the budget
- **THEN** remaining calls are refused, executed results are summarized, and the user sees which steps were skipped

### Requirement: Planning
For multi-step questions the agent SHALL first emit a short step plan (tool names + purpose), then execute stepwise, updating after each observation. The plan SHALL be visible in the transcript.

#### Scenario: Region stress question
- **WHEN** asked "stress status of region X last month"
- **THEN** a plan like `[geo_farm_report → geo_ask thresholds → summarize]` is shown before execution

### Requirement: Session state
Conversations SHALL persist in `agent.db` (separate from GeoMemory's DB): conversations, turns, tool-run references, artifacts. Restarting CLI/dashboard restores history.

#### Scenario: Resume
- **WHEN** the user restarts `geoagent chat`
- **THEN** previous conversations are listable and continuable

### Requirement: Abstention passthrough
When retrieval returns no evidence or grounding is insufficient, the agent SHALL abstain explicitly — stating why and offering next actions (ingest sources, widen filters) — never fabricating content.

#### Scenario: Empty knowledge base
- **WHEN** the user asks a domain question before any ingest
- **THEN** answer states no indexed evidence exists and suggests `geo_ingest`

### Requirement: Bilingual responses
Prompts SHALL instruct the model to answer in the language of the user turn (fa/en). Tool arguments remain English identifiers.

#### Scenario: Persian question
- **WHEN** the question is in Persian
- **THEN** the final answer is in Persian while citations/locators stay unchanged

### Requirement: Settings
Agent settings (provider, budgets, sandbox roots, registry/playbook paths) SHALL live in `<workspace>/agent.yaml`, overridable via CLI flags.

## Non-goals

- Local LLM runtimes (v0.x); fine-tuning the LLM; multi-agent orchestration.
