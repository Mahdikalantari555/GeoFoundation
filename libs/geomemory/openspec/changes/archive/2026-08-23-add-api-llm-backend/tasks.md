# Tasks: add-api-llm-backend

- [x] Task 1: Add LLM settings fields to `WorkspaceSettings`
  - Acceptance: `llm_provider`, `llm_api_base_url`, `llm_api_key_env`, `llm_model_id`, `llm_context_window` exist with documented defaults; legacy-only workspace.yaml round-trips unchanged; `llm_context_window` validated (>=1024, <=200000).
  - Verify: `conda run -n ai python -m pytest tests/unit/test_workspace_settings.py -q` (extend existing settings tests)
  - Files: `src/geomemory/core/models.py`, `tests/unit/test_workspace_settings.py`

- [x] Task 2: Make `LlamaCppBackend.n_ctx` configurable
  - Acceptance: constructor accepts `n_ctx: int = 32768`; `_load()` uses it; existing callers compile untouched.
  - Verify: unit test asserting the value reaches `Llama(...)` via monkeypatch; full qa unit suite green.
  - Files: `src/geomemory/qa/llama_cpp_backend.py`, `tests/unit/test_llama_cpp_backend.py`

- [x] Task 3: Implement `ApiLLMBackend` (RED→GREEN)
  - Acceptance: implements `model_id`/`generate`/`count_tokens`; POSTs OpenAI-compatible chat request to `{base_url}/chat/completions` with bearer key from env var; parses chat and legacy response shapes; maps missing key / offline / HTTP error to clear exceptions for abstention path.
  - Verify: `conda run -n ai python -m pytest tests/unit/test_api_backend.py -q` with fake `http.server` gateway fixture (request shape + both response shapes + error cases).
  - Files: `src/geomemory/qa/api_backend.py`, `tests/unit/test_api_backend.py`

- [x] Task 4: Backend factory `build_llm_backend(settings)`
  - Acceptance: resolution order per design D3 (explicit provider → baseline fallback); api+offline refusal; api without base URL refused; llamacpp without model_path falls back to baseline null behavior; returns ChatService-ready backend plus computed token_budget from context window.
  - Verify: `tests/unit/test_backend_factory.py` covering every branch of the resolution table.
  - Files: `src/geomemory/qa/backend_factory.py`, `tests/unit/test_backend_factory.py`

- [x] Task 7: Kilo gateway integration test (opt-in)
  - Acceptance: no direct `LlamaCppBackend` construction in workspace.py; abstention reasons updated to name the blocking condition; persisted answers record resolved model id.
  - Verify: extend `tests/unit/test_workspace_ask.py` (or nearest existing) with provider-matrix cases; grep confirms no hardcoded construction remains.
  - Files: `src/geomemory/core/workspace.py`

- [x] Task 6: Doctor reporting
  - Acceptance: doctor output includes provider, model id, key env var set/unset (never value), context window.
  - Verify: `tests/unit/test_doctor.py` addition.
  - Files: `src/geomemory/services/doctor.py`, `tests/unit/test_doctor.py`

- [x] Task 7: Kilo gateway integration test (opt-in)
  - Acceptance: `tests/integration/test_kilo_gateway.py` marked `integration`, skipif `GEOMEMORY_LLM_API_KEY` unset; when run with key: real completion against `https://api.kilo.ai/api/gateway/v1` model `kilo-auto/free`, non-empty text, latency recorded, citation pipeline unaffected.
  - Verify: without key → skipped in default run; with key → passes locally (`GEOMEMORY_LLM_API_KEY=... conda run -n ai python -m pytest tests/integration/test_kilo_gateway.py -q -m integration`).
  - Files: `tests/integration/test_kilo_gateway.py`

- [x] Task 8: Gates
  - Acceptance: full suite green; `ruff check src tests` clean for touched files; `mypy --strict src/geomemory` introduces no new violations.
  - Verify: `conda run -n ai python -m pytest tests/ -q && conda run -n ai ruff check src tests && conda run -n ai python -m mypy --strict src/geomemory`
  - Files: none (verification only)

Dependencies: 1→(2,4), 2→(4), 3→(4), 4→5, 5→(6,7), all→8.
