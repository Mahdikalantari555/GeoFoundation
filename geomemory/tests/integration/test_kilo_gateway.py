"""Integration test for the Kilo gateway (opt-in, requires API key).

Runs only when ``GEOMEMORY_LLM_API_KEY`` is available. A ``.env`` file at the
repo root is loaded automatically so the test passes locally without manual
environment setup. The test is skipped silently in default CI runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from geomemory.core.models import GenerationRequest, WorkspaceSettings
from geomemory.qa.api_backend import ApiLLMBackend, default_kilo_base_url
from geomemory.qa.backend_factory import build_llm_backend

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_path = _PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

_KEY = os.environ.get("GEOMEMORY_LLM_API_KEY")
pytestmark = pytest.mark.integration
skipif_no_key = pytest.mark.skipif(
    not _KEY, reason="GEOMEMORY_LLM_API_KEY not set; skipping live Kilo gateway test"
)


@skipif_no_key
class TestKiloGateway:
    def test_real_completion(self):
        backend = ApiLLMBackend(
            model_id="kilo-auto/free",
            api_base_url=default_kilo_base_url(),
            api_key=_KEY,
        )
        result = backend.generate(GenerationRequest(prompt="Reply with the single word: pong"))
        assert result.text.strip()
        assert result.model_id == "kilo-auto/free"
        assert result.latency_ms >= 0
        assert result.abstained is False

    def test_factory_resolves_api(self):
        settings = WorkspaceSettings(
            name="ws",
            llm_provider="api",
            offline=False,
            llm_context_window=32768,
        )
        backend, token_budget = build_llm_backend(settings)
        assert backend.model_id == "kilo-auto/free"
        assert "kilo.ai" in backend.api_base_url
        assert token_budget > 0
