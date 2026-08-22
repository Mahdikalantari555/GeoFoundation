# ADR-0002: Embedding Model Strategy — GGUF via llama-cpp with hashing fallback

Status: Accepted (as implemented) · Date extracted: 2026-08-22

## Context

Text and vision embeddings are core to retrieval quality. Requirements: run locally on CPU, no API keys/telemetry, deterministic behavior for golden tests, graceful operation when models aren't installed.

## Decision

1. **Protocols first**: `embeddings/text_embedder.py` (`TextEmbedder`) and `vision_embedder.py` (`VisionEmbedder`) define the contract (`space_id`, `model_id`, embed methods).
2. **Production path**: GGUF models via **llama-cpp-python**:
   - text: default model id `nomic-embed-text-v2-moe` (`embeddings/llama_cpp_text.py`)
   - vision: default model id `olmoearth-nano` (`embeddings/llama_cpp_vision.py`, experimental)
3. **Fallback path**: `HashingTextEmbedder` — n-gram feature hashing, no dependencies, used when no GGUF is configured (tests, CI-ish environments).
4. Model file paths come from **workspace settings** (`workspace.yaml`), never hardcoded; loading is lazy and raises `ModelNotLoadedError` on misuse.
5. Embedding spaces are isolated per modality (`text.*` vs vision ids); vectors never cross spaces.

Vision embedding today has a `PlaceholderVisionEmbedder` stub; the real GGUF path exists but is flagged experimental in README.

## Consequences

- ✅ Fully offline embeddings; testable without any model binary.
- ✅ Swapping embedding models = changing settings + rebuilding index (manifest records `model_id`, dimension, checksum via `embedding_record` table).
- ❌ Re-embedding on model change is manual (`rebuild_index`) — no automatic migration of stale spaces yet.
- ❌ llama-cpp-python build complexity pushed into optional `ai` extra.
