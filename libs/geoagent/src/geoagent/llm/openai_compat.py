"""OpenAI-compatible Chat Completions backend (stdlib urllib, no SDK lock-in)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from geoagent.config import AgentSettings
from geoagent.llm.base import ChatResponse, LLMError, ToolCall


class OpenAICompatBackend:
    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings
        base = settings.provider.base_url.rstrip("/")
        if not base.endswith("/v1") and "/v1" not in base.rsplit("/", 1)[-1]:
            base = f"{base}/v1"
        self._url = f"{base}/chat/completions"
        self._api_key = settings.resolve_api_key()
        if not self._api_key:
            env = settings.provider.api_key_env
            raise LLMError(
                f"No API key configured. Set the {env} environment variable "
                f"or provider.api_key in agent.yaml."
            )

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self._settings.provider.model,
            "messages": messages,
            "temperature": self._settings.provider.temperature,
        }
        if tools:
            body["tools"] = tools
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._settings.provider.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            tail = ""
            try:
                tail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # noqa: BLE001, S110 - error path best effort
                pass
            hint = "check provider.api_key / OPENAI_API_KEY" if exc.code == 401 else "check base_url and model name"
            raise LLMError(f"provider returned HTTP {exc.code}: {tail} ({hint})") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"cannot reach LLM provider at {self._url}: {exc.reason}") from exc

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        raw_calls = message.get("tool_calls") or []
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", "{}"),
            )
            for tc in raw_calls
        ]
        return ChatResponse(content=message.get("content"), tool_calls=tool_calls)
