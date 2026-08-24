"""Agent settings: provider, budgets, sandbox — agent.yaml + env overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProviderSettings(BaseModel):
    """OpenAI-compatible chat completions endpoint configuration."""

    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str | None = None
    temperature: float = 0.2
    timeout_s: float = 120.0


class BudgetSettings(BaseModel):
    max_tool_calls: int = 8
    max_wall_seconds: float = 120.0
    max_iterations: int = 6


class CliToolOutputSettings(BaseModel):
    artifacts_glob: str | None = None
    parse: str = "none"  # none | text | json


class CliToolConfig(BaseModel):
    description: str
    params: dict[str, Any] = Field(default_factory=dict)
    argv: list[str]
    cwd: str | None = None
    timeout_s: float = 600.0
    outputs: CliToolOutputSettings = Field(default_factory=CliToolOutputSettings)


class AgentSettings(BaseModel):
    """Top-level agent configuration persisted as ``agent.yaml``."""

    workspace: Path = Field(default_factory=lambda: Path("./geoagent-workspace"))
    memory_workspace: str | None = None
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    budgets: BudgetSettings = Field(default_factory=BudgetSettings)
    sandbox_roots: list[str] = Field(default_factory=list)
    cli_tools: dict[str, CliToolConfig] = Field(default_factory=dict)

    def resolve_sandbox_roots(self) -> list[Path]:
        roots = [Path(p).resolve() for p in self.sandbox_roots]
        if not roots:
            roots = [self.workspace.resolve()]
        return roots

    def resolve_api_key(self) -> str | None:
        if self.provider.api_key:
            return self.provider.api_key
        return os.environ.get(self.provider.api_key_env)


DEFAULT_YAML = """\
workspace: ./{name}
memory_workspace: null  # path to a GeoMemory workspace (geomemory CLI init)
provider:
  base_url: https://api.openai.com/v1   # any OpenAI-compatible endpoint
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
budgets:
  max_tool_calls: 8
  max_wall_seconds: 120
  max_iterations: 6
sandbox_roots: []
"""


def write_default_config(path: Path, name: str = "geoagent-workspace") -> None:
    path.write_text(DEFAULT_YAML.format(name=name), encoding="utf-8")


def load_settings(config_path: str | Path) -> AgentSettings:
    raw: dict[str, Any] = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    if "OPENAI_BASE_URL" in os.environ:
        raw.setdefault("provider", {})["base_url"] = os.environ["OPENAI_BASE_URL"]
    settings = AgentSettings.model_validate(raw)
    cfg_dir = Path(config_path).resolve().parent
    ws = settings.workspace
    settings.workspace = (ws if ws.is_absolute() else (cfg_dir / ws)).resolve()
    return settings
