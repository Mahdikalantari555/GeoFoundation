"""llama.cpp adapter for local LLM inference."""

from __future__ import annotations

import hashlib
import time

from geomemory.core.models import GenerationRequest, GenerationResult


class LlamaCppBackend:
    """Wrap llama-cpp-python for local GGUF LLM generation.

    The model is loaded lazily on first use. Generation parameters
    (temperature, max_tokens, stop sequences) are configurable per request.
    """

    def __init__(self, model_path: str, *, model_id: str = "minicpm") -> None:
        self.model_path = model_path
        self._model_id = model_id
        self._llm = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _load(self) -> None:
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - optional dep
                raise ImportError(
                    "LlamaCppBackend requires llama-cpp-python. "
                    "Install with `pip install geomemory[ai]`."
                ) from exc
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=4096,
                verbose=False,
            )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a completion for a request."""
        self._load()
        assert self._llm is not None
        start = time.perf_counter()
        out = self._llm.create_completion(
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=request.stop_sequences or None,
        )
        text = out["choices"][0]["text"]
        latency_ms = int((time.perf_counter() - start) * 1000)
        prompt_hash = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
        return GenerationResult(
            text=text,
            prompt_hash=prompt_hash,
            model_id=self.model_id,
            tokens_used=int(out.get("usage", {}).get("completion_tokens", 0)),
            latency_ms=latency_ms,
            abstained=False,
        )

    def count_tokens(self, text: str) -> int:
        """Return the token count of a text."""
        self._load()
        assert self._llm is not None
        return len(self._llm.tokenize(text.encode("utf-8")))