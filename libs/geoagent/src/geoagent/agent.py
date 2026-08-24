"""Agent core: plan → tool-call loop with budgets, citations, abstention."""

from __future__ import annotations

import json
import re
import time
from typing import Any

from geoagent.config import AgentSettings
from geoagent.llm.base import ChatResponse, LLMBackend
from geoagent.registry import Registry, RunContext
from geoagent.store import Store

SYSTEM_PROMPT = """\
You are GeoAgent, a precise assistant for remote-sensing and farm-monitoring \
workflows. You act by calling tools.

Rules:
- Answer in the language of the user's message (Persian or English). Tool \
arguments are always English identifiers.
- For multi-step tasks, first output a short numbered plan (tool names + purpose), \
then execute it stepwise.
- Ground every domain claim in tool results using citation keys [S1], [S2], ... \
mapped to the hits returned by geo_search in this turn. Never cite keys you were \
not given.
- If evidence or required data is missing, say explicitly what is missing and \
suggest the next action (e.g. ingest sources, widen date range). Never fabricate.
- Be terse. Report artifact paths returned by tools."""

_CITATION_RE = re.compile(r"\[S(\d+)\]")


class AgentCore:
    def __init__(
        self,
        settings: AgentSettings,
        backend: LLMBackend,
        registry: Registry,
        store: Store,
    ) -> None:
        self.settings = settings
        self.backend = backend
        self.registry = registry
        self.store = store

    def chat(
        self,
        conversation_id: str,
        user_text: str,
        *,
        on_event: Any = None,
    ) -> str:
        def emit(text: str) -> None:
            if on_event:
                on_event(text)

        turn_id = self.store.add_turn(conversation_id, "user", user_text)
        ctx = RunContext(
            store=self.store,
            workspace_dir=self.settings.workspace,
            sandbox_roots=self.settings.resolve_sandbox_roots(),
            settings=self.settings,
            conversation_id=conversation_id,
            turn_id=turn_id,
            max_tool_calls=self.settings.budgets.max_tool_calls,
            deadline=time.monotonic() + self.settings.budgets.max_wall_seconds,
        )
        messages = self._build_messages(conversation_id, user_text)
        available_keys: set[str] = set()

        for _ in range(self.settings.budgets.max_iterations):
            response = self.backend.chat(messages, tools=self.registry.openai_tools())
            if not response.tool_calls:
                final = self._strip_invalid_citations(response.content or "", available_keys)
                self.store.add_turn(conversation_id, "assistant", final)
                return final

            messages.append(self._assistant_message(response))
            for call in response.tool_calls:
                result = self.registry.call(call.name, call.parsed_arguments(), ctx)
                keys = self._register_hits(call.name, result.value, available_keys)
                emit(f"[tool] {call.name} -> {result.status}" + (f" ({keys} citations)" if keys else ""))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(self._compact(result.model_dump()), default=str),
                    }
                )

        fallback = (
            "Turn budget exhausted before a final answer "
            f"({self.settings.budgets.max_iterations} iterations / "
            f"{ctx.calls_used} tool calls executed)."
        )
        self.store.add_turn(conversation_id, "assistant", fallback)
        return fallback

    def new_conversation(self, title: str) -> str:
        return self.store.create_conversation(title)

    def _build_messages(self, conversation_id: str, user_text: str) -> list[dict[str, Any]]:
        manifest = "\n".join(self.registry.manifest_lines())
        system = f"{SYSTEM_PROMPT}\n\nAvailable tools:\n{manifest}"
        history = [
            {"role": t["role"], "content": t["content"]}
            for t in self.store.turns(conversation_id)
            if t["role"] in ("user", "assistant")
        ]
        history[-1]["content"] = user_text
        return [{"role": "system", "content": system}, *history]

    @staticmethod
    def _assistant_message(response: ChatResponse) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ],
        }

    @staticmethod
    def _register_hits(tool_name: str, value: Any, available: set[str]) -> int:
        if isinstance(value, dict) and isinstance(value.get("hits"), list):
            hits = value["hits"]
            for i in range(1, len(hits) + 1):
                available.add(f"S{i}")
            return len(hits)
        return 0

    @staticmethod
    def _strip_invalid_citations(text: str, available: set[str]) -> str:
        removed = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal removed
            key = match.group(0)[1:-1]
            if key in available:
                return match.group(0)
            removed += 1
            return ""

        cleaned = _CITATION_RE.sub(repl, text)
        if removed:
            cleaned += f"\n\n[{removed} invalid citation key(s) stripped]"
        return cleaned

    @staticmethod
    def _compact(result: dict[str, Any], max_chars: int = 4000) -> dict[str, Any]:
        value = result.get("value")
        blob = json.dumps(value, default=str)
        if len(blob) > max_chars:
            value = {"truncated": True, "preview": blob[:max_chars]}
        return {
            "status": result.get("status"),
            "value": value,
            "error": result.get("error"),
            "artifacts": result.get("artifacts"),
        }


def build_backend(settings: AgentSettings) -> LLMBackend:
    from geoagent.llm import OpenAICompatBackend

    return OpenAICompatBackend(settings)
