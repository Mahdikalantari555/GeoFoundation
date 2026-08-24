"""Unit tests for the LLM backend factory resolution."""

from __future__ import annotations

import pytest

from geomemory.core.models import WorkspaceSettings
from geomemory.qa.backend import NullBackend
from geomemory.qa.backend_factory import (
    LLMBackendUnavailableError,
    build_llm_backend,
)
from geomemory.qa.llama_cpp_backend import LlamaCppBackend


def _settings(**kw):
    return WorkspaceSettings(name="ws", **kw)


class TestBackendFactory:
    def test_baseline_model_path_selects_llamacpp(self):
        s = _settings(model_path="/tmp/m.gguf")
        backend, budget = build_llm_backend(s)
        assert isinstance(backend, LlamaCppBackend)
        assert backend.n_ctx == 32768
        assert budget > 0

    def test_baseline_no_model_path_abstains(self):
        s = _settings()
        with pytest.raises(LLMBackendUnavailableError):
            build_llm_backend(s)

    def test_explicit_llamacpp_without_path_abstains(self):
        s = _settings(llm_provider="llamacpp")
        with pytest.raises(LLMBackendUnavailableError):
            build_llm_backend(s)

    def test_explicit_llamacpp_with_path(self):
        s = _settings(llm_provider="llamacpp", model_path="/tmp/m.gguf")
        backend, _ = build_llm_backend(s)
        assert isinstance(backend, LlamaCppBackend)

    def test_api_without_key_abstains(self, monkeypatch):
        monkeypatch.delenv("GEOMEMORY_LLM_API_KEY", raising=False)
        s = _settings(llm_provider="api", offline=False)
        with pytest.raises(LLMBackendUnavailableError, match="API key"):
            build_llm_backend(s)

    def test_api_offline_abstains(self, monkeypatch):
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "secret")
        s = _settings(llm_provider="api", offline=True)
        with pytest.raises(LLMBackendUnavailableError, match="Offline"):
            build_llm_backend(s)

    def test_api_with_key_builds(self, monkeypatch):
        monkeypatch.setenv("GEOMEMORY_LLM_API_KEY", "secret")
        s = _settings(llm_provider="api", offline=False)
        backend, budget = build_llm_backend(s)
        assert backend.model_id == "kilo-auto/free"
        # Kilo default base url is used when not set.
        assert "kilo.ai" in backend.api_base_url
        assert budget > 0

    def test_api_custom_base_url_and_model(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret")
        s = _settings(
            llm_provider="api",
            offline=False,
            llm_api_key_env="MY_KEY",
            llm_api_base_url="https://example.test/v1",
            llm_model_id="custom-model",
            llm_context_window=65536,
        )
        backend, budget = build_llm_backend(s)
        assert backend.api_base_url == "https://example.test/v1"
        assert backend.model_id == "custom-model"
        assert backend.context_window == 65536

    def test_token_budget_scales_with_context_window(self):
        small = _settings(model_path="/tmp/m.gguf", llm_context_window=4096)
        big = _settings(model_path="/tmp/m.gguf", llm_context_window=200000)
        _, b_small = build_llm_backend(small)
        _, b_big = build_llm_backend(big)
        assert b_big > b_small


def test_null_backend_exists_for_reference():
    assert NullBackend().model_id == "null"
