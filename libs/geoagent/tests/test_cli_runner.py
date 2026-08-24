"""CLI runner tests using sys.executable as a fake external tool."""

import sys

from geoagent.config import AgentSettings, CliToolConfig, CliToolOutputSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import cli_runner


def build(tmp_path, cfg_name: str, cfg: CliToolConfig):
    settings = AgentSettings(workspace=tmp_path / "ws", cli_tools={cfg_name: cfg})
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")
    registry = Registry()
    cli_runner.register_from_config(registry, settings)
    ctx = RunContext(store=store, workspace_dir=settings.workspace,
                     sandbox_roots=[settings.workspace], settings=settings)
    return ctx, registry, settings.workspace


def test_success_with_json_parse_and_artifacts(tmp_path):
    script = (
        "import json,sys,pathlib;"
        "args=sys.argv[1:];"
        "pathlib.Path('runs/out').mkdir(parents=True,exist_ok=True);"
        "pathlib.Path('runs/out/result.json').write_text('{\"ok\": true}');"
        "print(json.dumps({'bbox': args[-1]}))"
    )
    cfg = CliToolConfig(
        description="fake stress lib",
        params={"start_date": {"type": "string"}, "bbox": {"type": "string"}},
        argv=[sys.executable, "-c", script, "--start", "{start_date}", "--bbox", "{bbox}"],
        outputs=CliToolOutputSettings(artifacts_glob="runs/**/*.json", parse="json"),
    )
    ctx, reg, _ws = build(tmp_path, "run_stress_analysis", cfg)
    res = reg.call("run_stress_analysis", {"start_date": "2025-07-01", "bbox": "48.2,31.0,48.9,31.6"}, ctx)
    assert res.status == "ok", res.error
    assert res.value["exit_code"] == 0
    assert res.value["parsed"] == {"bbox": "48.2,31.0,48.9,31.6"}
    assert len(res.artifacts) == 1
    assert res.artifacts[0].sha256

    cached = reg.call("run_stress_analysis", {"start_date": "2025-07-01", "bbox": "48.2,31.0,48.9,31.6"}, ctx)
    assert cached.from_cache is True


def test_nonzero_exit_is_failed_with_stderr_tail(tmp_path):
    script = "import sys; print('boom-detail', file=sys.stderr); sys.exit(3)"
    cfg = CliToolConfig(description="failing lib", params={}, argv=[sys.executable, "-c", script])
    ctx, reg, _ws = build(tmp_path, "fail_tool", cfg)
    res = reg.call("fail_tool", {}, ctx)
    assert res.status == "failed"
    assert res.value["exit_code"] == 3
    assert "boom-detail" in res.error or "boom-detail" in res.value["stderr_tail"]


def test_dry_run_executes_nothing(tmp_path):
    script = "import pathlib; pathlib.Path('RAN').write_text('x')"
    cfg = CliToolConfig(description="marker lib", params={}, argv=[sys.executable, "-c", script])
    ctx, reg, ws = build(tmp_path, "marker_tool", cfg)
    res = reg.call("marker_tool", {"dry_run": True}, ctx)
    assert res.status == "ok"
    assert res.value["dry_run"] is True
    assert not (ws / "RAN").exists()
    real = reg.call("marker_tool", {}, ctx)
    assert real.status == "ok"
    assert (ws / "RAN").exists()


def test_shell_metacharacters_stay_literal(tmp_path):
    script = "import sys; open('seen.txt','w').write(sys.argv[1])"
    cfg = CliToolConfig(description="echo lib", params={"v": {"type": "string"}},
                        argv=[sys.executable, "-c", script, "{v}"])
    ctx, reg, ws = build(tmp_path, "echo_tool", cfg)
    evil = "a; rm -rf / && cat /etc/passwd"
    res = reg.call("echo_tool", {"v": evil}, ctx)
    assert res.status == "ok"
    assert (ws / "seen.txt").read_text() == evil


def test_invalid_param_type_rejected(tmp_path):
    cfg = CliToolConfig(description="typed lib",
                        params={"n": {"type": "integer"}}, argv=["true"])
    ctx, reg, _ws = build(tmp_path, "typed_tool", cfg)
    res = reg.call("typed_tool", {"n": "not-an-int"}, ctx)
    assert res.status == "validation_error"


def test_agent_yaml_cli_tools_roundtrip(tmp_path):
    from geoagent.config import load_settings, write_default_config

    root = tmp_path / "proj"
    root.mkdir()
    write_default_config(root / "agent.yaml")
    cfg_path = root / "agent.yaml"
    cfg_path.write_text(cfg_path.read_text() + """
cli_tools:
  run_stress_analysis:
    description: stress window analysis
    params:
      start_date: {type: string}
      end_date: {type: string}
      bbox: {type: string}
    argv: ["python", "-m", "stresslib", "--start", "{start_date}", "--end", "{end_date}", "--bbox", "{bbox}"]
    outputs: {artifacts_glob: "runs/**/*", parse: json}
""")
    settings = load_settings(cfg_path)
    settings.workspace.mkdir(parents=True, exist_ok=True)
    assert "run_stress_analysis" in settings.cli_tools
    assert settings.cli_tools["run_stress_analysis"].argv[1] == "-m"

    registry = Registry()
    cli_runner.register_from_config(registry, settings)
    assert "run_stress_analysis" in registry.names()
    tools = registry.openai_tools()
    fn = next(t for t in tools if t["function"]["name"] == "run_stress_analysis")
    assert set(fn["function"]["parameters"]["required"]) == {"start_date", "end_date", "bbox"}
