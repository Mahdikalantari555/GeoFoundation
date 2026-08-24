"""LLM backend protocol and message models."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class LLMError(Exception):
    """Raised when the LLM provider is unreachable or misconfigured."""


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str = "{}"

    def parsed_arguments(self) -> dict[str, Any]:
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


class ChatResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []


@runtime_checkable
class LLMBackend(Protocol):
    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse: ...
