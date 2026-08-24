"""LLMBackend protocol."""

from __future__ import annotations

from typing import Protocol

from geomemory.core.models import GenerationRequest, GenerationResult


class LLMBackend(Protocol):
    """Protocol for local LLM inference backends."""

    @property
    def model_id(self) -> str:
        """Identifier of the underlying model."""
        ...

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a completion for a request."""
        ...

    def count_tokens(self, text: str) -> int:
        """Return the token count of a text."""
        ...


class NullBackend:
    """A backend that always abstains — used for testing and fallback."""

    model_id = "null"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Return an abstaining result."""
        return GenerationResult(
            text="not found in selected sources",
            prompt_hash="",
            model_id=self.model_id,
            abstained=True,
        )

    def count_tokens(self, text: str) -> int:
        """Approximate token count."""
        return max(1, len(text) // 4)