"""CLI runner: turn config-declared external CLIs into registry tools.

Declared in agent.yaml::

    cli_tools:
      run_stress_analysis:
        description: Run the stress-analysis library for a window
        params:
          start_date: {type: string}
          end_date: {type: string}
          bbox: {type: string}
        argv: ["python", "-m", "stresslib", "--start", "{start_date}",
               "--end", "{end_date}", "--bbox", "{bbox}"]
        outputs: {artifacts_glob: "runs/stress/**/*", parse: json}

Values substitute into argv as literal list items — no shell interpretation.
"""

from __future__ import annotations

import glob
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from geoagent.config import AgentSettings, CliToolConfig
from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

STDOUT_TAIL = 2000


def _resolve(ctx: RunContext, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else ctx.workspace_dir / p


def _substitute_placeholders(part: str, args: dict[str, Any]) -> str:
    out = part
    for key, val in args.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def _object_schema(params: dict[str, Any]) -> dict[str, Any]:
    props = {
        name: ({"type": spec} if isinstance(spec, str) else dict(spec))
        for name, spec in params.items()
    }
    required = [n for n, s in props.items() if s.get("required", True)]
    for s in props.values():
        s.pop("required", None)
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def register_from_config(registry: Registry, settings: AgentSettings) -> None:
    for tool_name, cfg in settings.cli_tools.items():
        _register_one(registry, settings, tool_name, cfg)


def _register_one(
    registry: Registry, settings: AgentSettings, tool_name: str, cfg: CliToolConfig
) -> None:
    schema = _object_schema(cfg.params)
    schema["properties"]["dry_run"] = {
        "type": "boolean",
        "description": "return expanded argv without executing",
    }

    @registry.register(
        ToolDefinition(
            name=tool_name,
            description=cfg.description,
            params=schema,
            returns="exit_code, parsed output, artifact paths",
            timeout_s=cfg.timeout_s,
            cacheable=True,
        )
    )
    def run_cli(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        dry_run = bool(args.pop("dry_run", False))
        argv = [_substitute_placeholders(part, args) for part in cfg.argv]
        if dry_run:
            return ToolResult(status="ok", value={"dry_run": True, "argv": argv})

        cwd = _resolve(ctx, cfg.cwd) if cfg.cwd else ctx.workspace_dir
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=cfg.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(status="timeout", error=f"{tool_name} exceeded {cfg.timeout_s:.0f}s")

        artifacts: list[ArtifactRef] = []
        if cfg.outputs.artifacts_glob:
            pattern = cfg.outputs.artifacts_glob
            matches = sorted(glob.glob(str(cwd / pattern), recursive=True))
            for m in matches[:50]:
                p = Path(m)
                if p.is_file():
                    digest = hashlib.sha256(p.read_bytes()).hexdigest()
                    artifacts.append(ArtifactRef(path=str(p), sha256=digest))

        value: dict[str, Any] = {
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout[-STDOUT_TAIL:],
            "stderr_tail": proc.stderr[-STDOUT_TAIL:],
            "artifacts": [a.path for a in artifacts],
        }
        if proc.returncode != 0:
            return ToolResult(
                status="failed",
                error=f"exit {proc.returncode}: {proc.stderr[-500:] or proc.stdout[-500:]}",
                value=value,
                artifacts=artifacts,
            )
        parse = cfg.outputs.parse
        if parse == "json":
            try:
                value["parsed"] = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                return ToolResult(
                    status="failed",
                    error=f"stdout is not valid JSON ({exc})",
                    value=value,
                    artifacts=artifacts,
                )
        elif parse == "text":
            value["parsed"] = proc.stdout.strip()
        return ToolResult(status="ok", value=value, artifacts=artifacts)
