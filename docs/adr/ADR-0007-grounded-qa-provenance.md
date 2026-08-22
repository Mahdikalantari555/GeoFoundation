# ADR-0007: Grounded QA with citations and abstention

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

Research assistants must trust answers. Un-grounded LLM output is worse than no answer for scientific work. Requirements from project spec: answers cite exact source locations; system abstains when evidence is insufficient; every QA interaction is auditable.

## Decision

`qa/chat_service.ChatService.ask()` pipeline:

1. Retrieve evidence via the hybrid search stack (`top_k` candidates).
2. Pack into a token-budgeted context block (`retrieval/context_packer.py`).
3. Build mode-specific prompt (`grounded_qa` | `research` | `code`) via `qa/prompts.py`.
4. Generate with an `LLMBackend` — `LlamaCppBackend` (GGUF, default model id `minicpm`) or `NullBackend` which always abstains when no model is configured.
5. **Citations**: numbered `[n]` keys extracted from the answer text, mapped to source segments (`citation.map_citations`), validated against retrieved hits (`validate_citations`).
6. **Abstention**: `should_abstain()` detects insufficient-evidence phrasing → result flagged / `AbstentionError` raised rather than hallucinated content.
7. **Persistence**: full audit row set — `conversation`, `turn`, `answer` (with `prompt_hash`, `model`, `abstained`), `citation` rows linking to `segment.locator`.

Provenance closes the loop back to raw bytes: `answer → citation → segment → asset_revision(hash) → objects/<sha256>`.

## Consequences

- ✅ Verifiable answers; citation correctness and faithfulness are measurable (`eval/qa_metrics.py: citation_correctness, faithfulness_proxy, abstention_accuracy`).
- ✅ Graceful degradation without models (NullBackend) keeps library usable everywhere.
- ❌ Citation mapping is string/regex-based today; malformed `[n]` usage degrades silently to fewer citations.
- ❌ Abstention heuristics are English-pattern based; Persian (`fa`) support declared in settings but not yet handled by abstention logic.
