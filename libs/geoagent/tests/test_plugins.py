"""Custom-tool plugin discovery tests."""

from geoagent.config import AgentSettings
from geoagent.plugins import load_plugin_module, load_plugins
from geoagent.registry import Registry

GOOD_PLUGIN = """\
from geoagent.registry import Registry, ToolDefinition


def register(registry):
    @registry.register(ToolDefinition(name="plugin_hello", description="h"))
    def plugin_hello(args, ctx):
        return {"hello": True}
"""

BROKEN_PLUGIN = "this is not python ((("


def _settings(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    (settings.workspace / "plugins").mkdir(parents=True)
    return settings


def test_workspace_plugin_discovered(tmp_path):
    settings = _settings(tmp_path)
    (settings.workspace / "plugins" / "hello.py").write_text(GOOD_PLUGIN)
    registry = Registry()
    loaded = load_plugins(registry, settings.workspace)
    assert loaded == ["plugin:hello"]
    assert "plugin_hello" in registry.names()


def test_broken_plugin_isolated(tmp_path):
    settings = _settings(tmp_path)
    (settings.workspace / "plugins" / "aaa_good.py").write_text(GOOD_PLUGIN)
    (settings.workspace / "plugins" / "zzz_bad.py").write_text(BROKEN_PLUGIN)
    registry = Registry()
    loaded = load_plugins(registry, settings.workspace)
    assert loaded == ["plugin:aaa_good"]


def test_load_plugin_module_returns_none_for_garbage(tmp_path):
    junk = tmp_path / "junk.py"
    junk.write_text(BROKEN_PLUGIN)
    assert load_plugin_module(junk) is None
