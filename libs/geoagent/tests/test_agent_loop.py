"""Agent loop tests with a scripted fake backend (no network)."""


from geoagent.agent import AgentCore
from geoagent.config import AgentSettings
from geoagent.llm.base import ChatResponse, ToolCall
from geoagent.registry import Registry, ToolDefinition
from geoagent.store import Store


class FakeBackend:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": messages, "tools": tools})
        return self.script.pop(0)


def build_core(tmp_path, backend):
    settings = AgentSettings(workspace=tmp_path / "ws")
    settings.workspace.mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")
    registry = Registry()
    register_test_tools(registry)
    return AgentCore(settings, backend, registry, store)


def register_test_tools(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="echo_hits",
            description="returns canned hits",
            cacheable=False,
        )
    )
    def echo_hits(args, ctx):
        from geoagent.registry import ToolResult

        return ToolResult(status="ok", value={"hits": [{"id": "seg1"}, {"id": "seg2"}]})

    @registry.register(
        ToolDefinition(
            name="boom",
            description="always fails",
        )
    )
    def boom(args, ctx):
        raise RuntimeError("kaboom")


def test_tool_loop_then_answer_with_citation_strip(tmp_path):
    backend = FakeBackend(
        [
            ChatResponse(
                content=None,
                tool_calls=[ToolCall(id="c1", name="echo_hits", arguments="{}")],
            ),
            ChatResponse(content="NDVI dropped [S1] but [S9] is fake."),
        ]
    )
    core = build_core(tmp_path, backend)
    conv = core.new_conversation("t")
    events = []
    answer = core.chat(conv, "status?", on_event=events.append)

    assert "[S1]" in answer
    assert "[S9]" not in answer
    assert "invalid citation" in answer
    assert any("echo_hits -> ok" in e for e in events)
    turns = core.store.turns(conv)
    assert turns[-1]["role"] == "assistant"


def test_failed_tool_reported_to_llm(tmp_path):
    backend = FakeBackend(
        [
            ChatResponse(tool_calls=[ToolCall(id="c1", name="boom", arguments="{}")]),
            ChatResponse(content="the tool failed; I abstain."),
        ]
    )
    core = build_core(tmp_path, backend)
    conv = core.new_conversation("t")
    answer = core.chat(conv, "run it")

    assert answer == "the tool failed; I abstain."
    tool_msg = next(
        m for m in backend.calls[-1]["messages"] if m.get("role") == "tool"
    )
    assert "kaboom" in tool_msg["content"]


def test_budget_exhaustion_fallback(tmp_path):
    backend = FakeBackend(
        [
            ChatResponse(tool_calls=[ToolCall(id=f"c{i}", name="echo_hits", arguments="{}")])
            for i in range(10)
        ]
    )
    backend.settings_hack = True
    core = build_core(tmp_path, backend)
    core.settings.budgets.max_iterations = 2
    conv = core.new_conversation("t")
    answer = core.chat(conv, "loop forever")
    assert "budget exhausted" in answer


def test_history_included(tmp_path):
    backend = FakeBackend([ChatResponse(content="first ok"), ChatResponse(content="second ok")])
    core = build_core(tmp_path, backend)
    conv = core.new_conversation("t")
    core.chat(conv, "first question")
    core.chat(conv, "second question")
    msgs = backend.calls[-1]["messages"]
    contents = [m["content"] for m in msgs]
    assert "first question" in contents and "second question" in contents
    assert any(m["role"] == "system" and "Available tools" in m["content"] for m in msgs)
