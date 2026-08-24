"""Tests for workspace settings persistence and env overrides."""

from __future__ import annotations

import yaml

from geomemory.core.config import ENV_OVERRIDES, load_settings, save_settings
from geomemory.core.models import WorkspaceSettings


class TestEnvOverrides:
    def test_vision_path_env_override(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "workspace.yaml"
        settings = WorkspaceSettings(name="test")
        save_settings(settings_path, settings)

        monkeypatch.setenv("GEOMEMORY_VISION_PATH", "/opt/models/olmoearth.pth")
        loaded = load_settings(settings_path)
        assert loaded.vision_path == "/opt/models/olmoearth.pth"

    def test_vision_path_env_overrides_yaml(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "workspace.yaml"
        data = {"name": "test", "vision_path": "/old/path.pth"}
        settings_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        monkeypatch.setenv("GEOMEMORY_VISION_PATH", "/new/path.pth")
        loaded = load_settings(settings_path)
        assert loaded.vision_path == "/new/path.pth"

    def test_vision_path_no_env_keeps_yaml(self, tmp_path, monkeypatch):
        settings_path = tmp_path / "workspace.yaml"
        data = {"name": "test", "vision_path": "/existing.pth"}
        settings_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        monkeypatch.delenv("GEOMEMORY_VISION_PATH", raising=False)
        loaded = load_settings(settings_path)
        assert loaded.vision_path == "/existing.pth"

    def test_env_override_map_contains_vision_path(self):
        assert "GEOMEMORY_VISION_PATH" in ENV_OVERRIDES
        assert ENV_OVERRIDES["GEOMEMORY_VISION_PATH"] == "vision_path"
