"""Workspace settings persistence (workspace.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from geomemory.core.models import WorkspaceSettings


def save_settings(path: str | Path, settings: WorkspaceSettings) -> None:
    """Write settings to a YAML file atomically."""
    target = Path(path)
    tmp = target.with_suffix(".tmp")
    data = settings.model_dump()
    with tmp.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
    tmp.replace(target)


def load_settings(path: str | Path) -> WorkspaceSettings:
    """Load settings from a YAML file."""
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return WorkspaceSettings(**data)


def default_settings(name: str = "GeoMemory Workspace") -> WorkspaceSettings:
    """Return default settings for a new workspace."""
    return WorkspaceSettings(name=name)


def settings_from_dict(data: dict[str, Any]) -> WorkspaceSettings:
    """Build settings from an arbitrary dict (optionally validating known keys)."""
    return WorkspaceSettings(**data)