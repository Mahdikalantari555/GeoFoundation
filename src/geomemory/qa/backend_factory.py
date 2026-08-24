"""Factory that resolves the configured LLM backend from workspace settings."""

from __future__ import annotations

import os

from geomemory.core.exceptions import AbstentionError
from geomemory.core.models import WorkspaceSettings
from geomemory.qa.api_backend import ApiLLMBackend, default_kilo_base_url
from geomemory.qa.backend import LLMBackend
from geomemory.qa.llama_cpp_backend import LlamaCppBackend

_PROMPT_OVERHEAD = 512
_MAX_TOKENS_DEFAULT = 512


class LLMBackendUnavailableError(AbstentionError):
    """Raised when no LLM backend can be resolved from settings."""


def _token_budget_for(context_window: int) -> int:
    available = context_window - _MAX_TOKENS_DEFAULT - _PROMPT_OVERHEAD
    return available if available > 0 else _PROMPT_OVERHEAD


def build_llm_backend(
    settings: WorkspaceSettings,
) -> tuple[LLMBackend, int]:
    """Resolve the LLM backend (and computed token budget) from settings.

    Resolution order:
      1. Explicit ``llm_provider``: build that backend, validating prerequisites.
      2. Unset: baseline — llama.cpp if ``model_path`` configured, else abstain.

    Raises ``LLMBackendUnavailableError`` (an ``AbstentionError`` subclass) when no
    backend can be constructed, so callers can convert it into an abstaining
    answer with a clear reason. Offline mode blocks the remote API backend.
    """
    context_window = settings.llm_context_window
    token_budget = _token_budget_for(context_window)
    provider = settings.llm_provider

    if provider == "api":
        if settings.offline:
            raise LLMBackendUnavailableError(
                "Offline mode is enabled; remote LLM API backend is not available. "
                "Set offline: false to use a gateway."
            )
        env_var = settings.llm_api_key_env
        api_key = os.environ.get(env_var, "")
        if not api_key:
            raise LLMBackendUnavailableError(
                f"LLM API key not found in environment variable {env_var!r}. "
                "Set it before using the API backend."
            )
        base_url = settings.llm_api_base_url or default_kilo_base_url()
        backend: LLMBackend = ApiLLMBackend(
            model_id=settings.llm_model_id,
            api_base_url=base_url,
            api_key=api_key,
            context_window=context_window,
        )
        return backend, token_budget

    if provider == "llamacpp":
        if not settings.model_path:
            raise LLMBackendUnavailableError(
                "LLM provider set to llama-cpp but model_path is not configured."
            )
        return (
            LlamaCppBackend(settings.model_path, n_ctx=context_window),
            token_budget,
        )

    if provider is None:
        if settings.model_path:
            return (
                LlamaCppBackend(settings.model_path, n_ctx=context_window),
                token_budget,
            )
        raise LLMBackendUnavailableError(
            "No LLM backend configured. Set llm_provider=api (with the API key), "
            "or model_path for a local GGUF model."
        )

    raise LLMBackendUnavailableError(f"Unknown llm_provider: {provider!r}")
