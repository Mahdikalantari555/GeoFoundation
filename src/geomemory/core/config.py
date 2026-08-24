"""Workspace settings persistence (workspace.yaml)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from geomemory.core.models import WorkspaceSettings

# Environment variables that override workspace settings when set.
ENV_OVERRIDES: dict[str, str] = {
    "GEOMEMORY_QDRANT_URL": "qdrant_url",
    "GEOMEMORY_ST_MODEL": "st_model_name",
    "GEOMEMORY_EMBEDDING_BACKEND": "embedding_backend",
    "GEOMEMORY_VECTOR_BACKEND": "vector_backend",
    "GEOMEMORY_VISION_PATH": "vision_path",
}


def _apply_env_overrides(settings: WorkspaceSettings) -> WorkspaceSettings:
    """Return settings with documented environment overrides applied."""
    changes: dict[str, Any] = {}
    for env_var, field in ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value is not None:
            changes[field] = value
    if not changes:
        return settings
    merged = settings.model_dump()
    merged.update(changes)
    return WorkspaceSettings(**merged)


def save_settings(path: str | Path, settings: WorkspaceSettings) -> None:
    """Write settings to a YAML file atomically."""
    target = Path(path)
    tmp = target.with_suffix(".tmp")
    data = settings.model_dump()
    with tmp.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
    tmp.replace(target)


def load_settings(path: str | Path) -> WorkspaceSettings:
    """Load settings from a YAML file, applying documented env overrides."""
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    settings = WorkspaceSettings(**data)
    return _apply_env_overrides(settings)


def default_settings(name: str = "GeoMemory Workspace") -> WorkspaceSettings:
    """Return default settings for a new workspace."""
    return WorkspaceSettings(name=name)


def settings_from_dict(data: dict[str, Any]) -> WorkspaceSettings:
    """Build settings from an arbitrary dict (optionally validating known keys)."""
    return WorkspaceSettings(**data)
