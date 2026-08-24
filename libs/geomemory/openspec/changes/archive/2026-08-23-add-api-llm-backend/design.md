# Design: add-api-llm-backend

## Context

`Workspace.ask` (src/geomemory/core/workspace.py:563) currently hardcodes the backend chain:
`settings.model_path` → `LlamaCppBackend(model_path)` → `ChatService`. `ChatService`
(src/geomemory/qa/chat_service.py) already treats the backend as an opaque object with
`model_id` / `generate(GenerationRequest) -> GenerationResult` — the `LLMBackend` protocol seam.
Only `_load()`'s hardcoded `n_ctx=4096` and the missing api implementation block reuse.

## Goals / Non-Goals

- Goals: provider-pluggable QA; bigger configurable context window; zero new runtime deps; secret hygiene; GeoAgent-ready seam.
- Non-Goals: streaming responses, multi-turn chat memory, tool calling (GeoAgent's job), retries/backoff beyond one clear failure path, key management tooling.

## Decisions

### D1. Stdlib HTTP, no new dependency
`urllib.request` + `json` cover POST-with-bearer + JSON parse. Keeps core install torch-free
*and* httpx-free, matching repo invariant "heavy/network deps stay behind lazy imports" — here,
no dep at all. Timeout default 120s, overridable via `GEOMEMORY_LLM_TIMEOUT` env (seconds).

### D2. Endpoint = base_url + `/chat/completions`
Default `llm_api_base_url = "https://api.kilo.ai/api/gateway/v1"` so request URL is
`.../v1/chat/completions` — standard OpenAI-compatible layout. Any other OpenAI-style gateway
works by changing base URL only. Request body uses chat format (`messages=[{role:"user", content:prompt}]`,
plus `stop`, `temperature`, `max_tokens`). Response parsing reads `choices[0].message.content`
with fallback to legacy `choices[0].text`.

### D3. Provider resolution order (Workspace.ask)
1. `settings.llm_provider` explicit → build that backend (validate combo: `api` needs base URL;
   `llamacpp` needs `model_path`; violations ⇒ abstention with reason).
2. Unset → baseline: `llamacpp` iff `model_path` else null-abstain. Byte-for-byte compatible.
3. `offline=True` forces refusal for `api` before any network I/O.

Factory lives as module function `build_llm_backend(settings) -> LLMBackendLike` in
`geomemory/qa/backend_factory.py` so CLI/doctor/tests share it (single canonical path).

### D4. Context window plumbing
`llm_context_window` (default 32768, validated ≤ 200000):
- `LlamaCppBackend(..., n_ctx=settings.llm_context_window)` — parameter added, old positional calls unaffected.
- `ChatService(token_budget=min(default_budget, window - max_tokens - overhead))` computed in factory;
  `per_hit_budget` unchanged (500). Overhead constant 512 tokens (system prompt + question + slack).
- `GenerationRequest.max_tokens` stays 512 default.

### D5. Secrets
Key read at call time: `os.environ[settings.llm_api_key_env]`. Never logged, never persisted.
Doctor prints "set"/"not set" only. Missing key ⇒ abstention reason includes env var name.

### D6. count_tokens approximation for api backend
No local tokenizer for hosted models ⇒ heuristic `max(1, len(text) // 4)`. Documented as
approximate; only used for budgeting, never billing claims. `LlamaCppBackend.count_tokens`
stays exact (real tokenizer).

### D7. Testing strategy (TDD)
- Unit (no network): fake gateway via `http.server` on ephemeral port in fixture; assert request shape
  (auth header present when key set in test env var), response mapping, error→abstention mapping,
  offline refusal, budget math (4k vs 32k packing), settings round-trip.
- Integration (`@pytest.mark.integration`, skipif no `GEOMEMORY_LLM_API_KEY`): real Kilo gateway,
  model `kilo-auto/free`, asserts non-empty completion + latency recorded. Skipped silently otherwise — CI-safe.

## Risks / Trade-offs

- [Gateway response drift] → tolerant parser (chat + legacy completions shapes); unit tests pin both.
- [Token estimate mismatch wastes window] → conservative 512-token overhead headroom; worst case packs slightly less evidence, never truncates mid-answer.
- [Users expect key in yaml] → rejected by design (D5); doctor message explains env var name.

## Migration Plan

Purely additive settings. Existing workspaces open untouched; behavior identical until user sets new fields. No data migration.

## Open Questions

(none — resolved in explore: Kilo gateway confirmed, `kilo-auto/free` default model, key provided later by user.)
