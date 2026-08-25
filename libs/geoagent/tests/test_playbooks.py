"""Playbook engine tests with dummy chained tools."""

import pytest

from geoagent import playbooks as pb_mod
from geoagent.config import AgentSettings
from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)
from geoagent.store import Store

SAMPLE = """\
---
name: demo-chain
version: 1
triggers: ["demo chain"]
params:
  input_tif: {type: string}
steps:
  - tool: make_raster
    args:
      path: "{{params.input_tif}}"
      tag: pre-{{params.input_tif}}
  - tool: consume_raster
    args:
      src: "{{steps.0.artifacts.0.path}}"
---

Demo description.
"""


@pytest.fixture()
def env(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    ws = settings.workspace
    ws.mkdir(parents=True)
    store = Store(ws / "agent.db")
    registry = Registry()

    @registry.register(
        ToolDefinition(name="make_raster", description="m",
                       params={"type": "object", "properties": {"path": {"type": "string"}, "tag": {"type": "string"}}})
    )
    def make_raster(args, ctx):
        out = ctx.workspace_dir / args["path"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(args["tag"])
        return ToolResult(status="ok", value={"made": str(out)},
                          artifacts=[ArtifactRef(path=str(out))])

    @registry.register(
        ToolDefinition(name="consume_raster", description="c",
                       params={"type": "object", "properties": {"src": {"type": "string"}}})
    )
    def consume_raster(args, ctx):
        return ToolResult(status="ok", value={"consumed": args["src"], "bytes": len(open(args["src"]).read())})

    ctx = RunContext(store=store, workspace_dir=ws,
                     sandbox_roots=[ws], settings=settings)
    return settings, registry, ctx, ws


def test_parse_and_validate(env):
    _settings, registry, _ctx, _ws = env
    pb = pb_mod.parse_playbook(SAMPLE, "sample.md")
    assert pb.name == "demo-chain"
    assert pb_mod.validate_playbook(pb, registry) == []


def test_validation_catches_unknown_tool_and_bad_refs(tmp_path):
    registry = Registry()
    bad = """---
name: broken
steps:
  - tool: ghost_tool
    args: {a: "{{params.missing}}"}
  - tool: also_ghost
    args: {b: "{{steps.9.value.x}}"}
---"""
    pb = pb_mod.parse_playbook(bad, "bad.md")
    problems = pb_mod.validate_playbook(pb, registry)
    assert any("unknown tool 'ghost_tool'" in p for p in problems)
    assert any("not declared in params" in p for p in problems)
    assert any("later/own step" in p for p in problems)


def test_playbook_registers_as_tool_and_runs_chain(env):
    settings, registry, ctx, ws = env
    (ws / "playbooks").mkdir()
    (ws / "playbooks" / "demo-chain.md").write_text(SAMPLE, encoding="utf-8")

    pb_mod.register_playbook_tools(registry, settings)
    assert "pb_demo_chain" in registry.names()

    res = registry.call("pb_demo_chain", {"input_tif": "in/a.tif"}, ctx)
    assert res.status == "ok", res.error
    step_values = res.value["steps"]
    assert step_values[1]["value"]["consumed"].endswith("in/a.tif")
    assert step_values[1]["value"]["bytes"] == len("pre-in/a.tif")
    cached = registry.call("pb_demo_chain", {"input_tif": "in/a.tif"}, ctx)
    assert cached.from_cache is True


def test_invalid_playbook_tool_reports_not_crashes(env):
    settings, registry, ctx, ws = env
    text = SAMPLE.replace("make_raster", "ghost_step_tool").replace("demo-chain", "broken-chain")
    (ws / "playbooks").mkdir(exist_ok=True)
    (ws / "playbooks" / "broken-chain.md").write_text(text, encoding="utf-8")

    pb_mod.register_playbook_tools(registry, settings)
    assert "pb_broken_chain" in registry.names()
    res = registry.call("pb_broken_chain", {"input_tif": "x"}, ctx)
    assert res.status == "validation_error"
    assert "invalid" in res.error


def test_partial_template_substitution():
    out = pb_mod._substitute("pre-{{params.x}}-post", {"x": 7}, [])
    assert out == "pre-7-post"


def test_typed_passthrough_keeps_non_string_values():
    out = pb_mod._substitute({
        "n": "{{params.count}}",
        "nested": {"rules": [{"min": -1, "max": "{{params.cut}}"}]},
    }, {"count": 3, "cut": 0.4}, [])
    assert out == {"n": 3, "nested": {"rules": [{"min": -1, "max": 0.4}]}}


def test_missing_frontmatter_rejected():
    with pytest.raises(pb_mod.PlaybookError):
        pb_mod.parse_playbook("no frontmatter here")


def test_draft_and_save_roundtrip(env):
    _settings, _registry, _ctx, ws = env
    (ws / "playbooks").mkdir(exist_ok=True)

    class FakeBackend:
        def chat(self, messages, tools=None):
            assert "make_raster" in messages[0]["content"]
            from geoagent.llm.base import ChatResponse

            return ChatResponse(content=SAMPLE)

    saved = pb_mod.save_playbook(
        ws, "demo chain", pb_mod.draft_playbook_text(FakeBackend(), "demo chain",
                                                     [{"tool": "make_raster", "args": {}}])
    )
    assert saved.exists()
    assert pb_mod.parse_playbook(saved.read_text(encoding="utf-8")).name == "demo-chain"
