"""Unit tests for LlamaCppBackend: configurable n_ctx."""

from __future__ import annotations

import sys
import types

import pytest

from geomemory.core.models import GenerationRequest
from geomemory.qa.llama_cpp_backend import LlamaCppBackend


class _FakeLlama:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def create_completion(self, **kwargs):
        return {
            "choices": [{"text": "hi"}],
            "usage": {"completion_tokens": 1},
        }

    def tokenize(self, text):
        return b"x" * len(text)


@pytest.fixture()
def fake_llama_cpp(monkeypatch):
    mod = types.ModuleType("llama_cpp")
    mod.Llama = _FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", mod)
    yield mod


class TestLlamaCppBackend:
    def test_n_ctx_reaches_loader(self, fake_llama_cpp):
        backend = LlamaCppBackend("/tmp/m.gguf", n_ctx=8192)
        backend._load()
        assert backend._llm.kwargs["n_ctx"] == 8192

    def test_default_n_ctx(self, fake_llama_cpp):
        backend = LlamaCppBackend("/tmp/m.gguf")
        backend._load()
        assert backend._llm.kwargs["n_ctx"] == 32768

    def test_generate_returns_result(self, fake_llama_cpp):
        backend = LlamaCppBackend("/tmp/m.gguf", n_ctx=4096)
        result = backend.generate(GenerationRequest(prompt="q"))
        assert result.text == "hi"
        assert result.model_id == "minicpm"
        assert result.abstained is False

    def test_missing_extra_message(self, monkeypatch):
        # Simulate the optional dependency being absent.
        monkeypatch.setitem(sys.modules, "llama_cpp", None)
        backend = LlamaCppBackend("/tmp/m.gguf")
        with pytest.raises(ImportError, match="llama-cpp-python"):
            backend._load()
