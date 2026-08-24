"""OpenAI-compatible HTTP LLM backend (no new dependencies)."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from geomemory.core.exceptions import AbstentionError
from geomemory.core.models import GenerationRequest, GenerationResult

_KILO_DEFAULT_BASE_URL = "https://api.kilo.ai/api/gateway/v1"
_PROMPT_OVERHEAD = 512
_MAX_TOKENS_DEFAULT = 512


class ApiLLMBackend:
    """LLM backend that calls an OpenAI-compatible gateway over HTTP.

    Uses only the standard library: ``urllib.request`` for the POST and
    ``json`` for parsing. No third-party HTTP client is required, keeping
    the core package dependency-free.
    """

    def __init__(
        self,
        *,
        model_id: str,
        api_base_url: str,
        api_key: str,
        context_window: int = 32768,
        timeout: int | None = None,
    ) -> None:
        self._model_id = model_id
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.context_window = context_window
        self.timeout = (
            timeout
            if timeout is not None
            else int(os.environ.get("GEOMEMORY_LLM_TIMEOUT", "120"))
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
        url = self.api_base_url + "/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                raw = resp.read()
        except urllib.error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise AbstentionError(
                f"LLM gateway returned HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise AbstentionError(
                f"LLM gateway unreachable ({self.api_base_url}): {exc.reason}"
            ) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise AbstentionError("LLM gateway returned non-JSON response") from exc

    @staticmethod
    def _extract_text(response: dict[str, object]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""
        choice = choices[0]
        assert isinstance(choice, dict)
        # OpenAI chat format: {"message": {"content": ...}}
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
        # Legacy completion format: {"text": ...}
        if isinstance(choice.get("text"), str):
            return str(choice["text"])
        return ""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate a completion for a request via the gateway."""
        payload: dict[str, object] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences
        start = time.perf_counter()
        response = self._post(payload)
        text = self._extract_text(response)
        latency_ms = int((time.perf_counter() - start) * 1000)
        prompt_hash = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
        return GenerationResult(
            text=text,
            prompt_hash=prompt_hash,
            model_id=self.model_id,
            tokens_used=0,
            latency_ms=latency_ms,
            abstained=False,
        )

    def count_tokens(self, text: str) -> int:
        """Approximate token count (~4 chars/token); only used for budgeting."""
        return max(1, len(text) // 4)

    @property
    def token_budget(self) -> int:
        """Tokens available for retrieved context given the context window."""
        available = self.context_window - _MAX_TOKENS_DEFAULT - _PROMPT_OVERHEAD
        return available if available > 0 else _PROMPT_OVERHEAD


def default_kilo_base_url() -> str:
    """Return the default Kilo gateway base URL."""
    return _KILO_DEFAULT_BASE_URL
