# Proposal: add-api-llm-backend

## Why

Grounded QA currently works only with a local GGUF model: `LlamaCppBackend` hardcodes `n_ctx=4096`, and `Workspace.ask` constructs it unconditionally from `settings.model_path`. The 4k window caps how much retrieved evidence a grounded answer can use, and users whose workstation cannot run a GGUF model (or who prefer hosted models) have no path to `ask()` at all. GeoMemory is consumed by the GeoAgent product, which needs a configurable, provider-agnostic LLM seam.

## What Changes

- New `ApiLLMBackend` in `src/geomemory/qa/api_backend.py` implementing the existing `LLMBackend` protocol (`model_id`, `generate`, `count_tokens`) against any OpenAI-compatible chat-completions endpoint, using stdlib `urllib.request` (no new runtime dependency). Default endpoint: Kilo gateway (`https://api.kilo.ai/api/gateway/v1/chat/completions`), default model `kilo-auto/free`.
- Provider selection seam: new additive `WorkspaceSettings` fields (`llm_provider`, `llm_api_base_url`, `llm_api_key_env`, `llm_model_id`, `llm_context_window`). `Workspace.ask` builds the configured backend instead of hardcoding `LlamaCppBackend`. Unset fields preserve today's behavior exactly (llama.cpp when `model_path` set, abstain otherwise).
- API keys never stored in `workspace.yaml`; read from an environment variable named by `llm_api_key_env` (default `GEOMEMORY_LLM_API_KEY`). Missing key at ask-time ⇒ clean abstention with actionable reason, not a stack trace.
- Context window becomes configuration: `llm_context_window` (default 32768; values up to 200000 accepted) feeds both the llama.cpp `n_ctx` and the QA prompt budgeting so bigger windows admit more packed evidence. Hardcoded `n_ctx=4096` removed.
- Offline guard: when `settings.offline=True`, the api backend refuses with an explicit abstention reason (surfaced, not silent).
- `geomemory doctor` reports LLM backend resolution (provider resolved, key present/absent, endpoint reachable-check optional).
- Integration test against the real Kilo gateway runs only when `GEOMEMORY_LLM_API_KEY` is set (skip otherwise); unit tests use a local fake HTTP server.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities
- `grounded-qa`: adds requirements for pluggable LLM backend selection (null / llamacpp / api), API-based generation, context-window-aware prompt budgeting, offline guard, and missing-key abstention.
- `workspace-management`: adds requirement for LLM provider settings — new settings fields, environment-variable secret handling, backward-compatible defaults.

## Impact

- **Code**: `src/geomemory/core/models.py` (+5 `WorkspaceSettings` fields), `src/geomemory/core/workspace.py` (`Workspace.ask` backend factory), `src/geomemory/qa/api_backend.py` (new), `src/geomemory/qa/llama_cpp_backend.py` (configurable `n_ctx`), `src/geomemory/services/doctor.py` (report line).
- **APIs**: no breaking changes. Public facade unchanged (`ask()` signature identical). New settings keys are additive; absent keys reproduce current behavior.
- **Dependencies**: none added (stdlib `urllib.request`).
- **Systems**: api backend requires network at ask time and conflicts with `offline=True` by design — refusal is explicit. Secret hygiene: key lives in env var only.
- **Tests**: unit tests for backend selection + api backend via fake server + budget math; one opt-in integration test gated on `GEOMEMORY_LLM_API_KEY`.
