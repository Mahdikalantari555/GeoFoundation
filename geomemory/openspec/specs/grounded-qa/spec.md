# Grounded QA — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Requirements

### Requirement: Grounded answering
The system SHALL answer questions using retrieved workspace evidence via a prompt appropriate to the selected mode (`grounded_qa`, `research`, `code`).

#### Scenario: Answer with evidence
- **WHEN** `ask(question)` is called on a workspace with indexed content and a configured LLM backend
- **THEN** the returned `QAResult.text` is generated from packed context and carries citations

### Requirement: Citations
Answers SHALL map inline `[n]` markers to source segments, validated against retrieved hits; each citation persists with locator and optional claim span.

#### Scenario: Citation mapping
- **WHEN** the model emits `[2]` referring to context item 2
- **THEN** a citation row links answer → segment with locator metadata

### Requirement: Abstention
The system SHALL detect insufficient-evidence answers and flag abstention instead of presenting ungrounded content as fact.

#### Scenario: No model configured
- **WHEN** NullBackend is active (no GGUF configured)
- **THEN** generation abstains rather than fabricating content

### Requirement: Conversation persistence
Each ask SHALL record conversation, turn(s), answer (model id, prompt_hash, abstained flag), and citations.

#### Scenario: Audit trail
- **WHEN** any QA exchange completes
- **THEN** turn/answer/citation rows allow full replay of question → evidence → response

### Requirement: Pluggable LLM backend selection
`Workspace.ask` SHALL construct its generation backend from workspace settings (`llm_provider`) instead of hardcoding llama.cpp: `null` abstains, `llamacpp` uses the GGUF model at `settings.model_path`, `api` uses the configured OpenAI-compatible endpoint. When `llm_provider` is unset, behavior SHALL be unchanged from the baseline (llama.cpp iff `model_path` is set, otherwise abstain).

#### Scenario: Provider unset keeps baseline
- **WHEN** `ask()` runs in a workspace where `llm_provider` is not set and `model_path` points to a GGUF file
- **THEN** generation uses the local llama.cpp backend

#### Scenario: Explicit api provider
- **WHEN** `llm_provider: api` is configured with a base URL and model id
- **THEN** `ask()` routes generation through `ApiLLMBackend`
- **AND** `QAResult.model` reports the configured model id

### Requirement: API LLM backend
The system SHALL support generation via any OpenAI-compatible chat-completions endpoint using only stdlib HTTP, mapping `GenerationRequest` fields (prompt, max_tokens, temperature, stop sequences) onto the request and surfacing failures as QA abstention with a reason that names the failing condition (missing key, offline mode, HTTP error).

#### Scenario: Successful completion
- **WHEN** the api backend receives a `GenerationRequest` and the gateway returns a chat completion
- **THEN** `generate` returns a `GenerationResult` with text, model id, token usage, and latency

#### Scenario: Missing API key
- **WHEN** the environment variable named by `llm_api_key_env` is unset or empty
- **THEN** `ask()` abstains with reason "No API key configured (<env var name>)" without performing an HTTP request

#### Scenario: Offline guard
- **WHEN** `settings.offline` is true and `llm_provider` resolves to `api`
- **THEN** `ask()` abstains with an explicit offline refusal instead of attempting network access

### Requirement: Context-window-aware budgeting
The QA prompt budget SHALL derive from the configured context window (`llm_context_window`, default 32768): packed evidence budget = context window minus prompt overhead minus requested completion tokens. The local llama.cpp context size (`n_ctx`) SHALL come from the same setting rather than a hardcoded 4096.

#### Scenario: Larger window admits more evidence
- **WHEN** two identical workspaces are asked the same question, one with `llm_context_window=4096` and one with `32768`
- **THEN** the 32k workspace packs at least as much retrieved evidence into the prompt as the 4k one

#### Scenario: Default preserved for local models
- **WHEN** no `llm_context_window` is configured
- **THEN** llama.cpp loads with the documented default (32768) and QA budgeting matches it
