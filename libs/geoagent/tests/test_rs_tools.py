"""Tests for the GeoAgent METRIC remote-sensing tool."""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest
from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store


class FakeMETRICPipeline:
    instances: ClassVar[list[FakeMETRICPipeline]] = []

    def __init__(self, config):
        self.config = config
        self.calls: list[dict] = []
        self.instances.append(self)

    def run(self, landsat_dir, meteo_data, output_dir):
        self.calls.append(
            {
                "landsat_dir": landsat_dir,
                "meteo_data": meteo_data,
                "output_dir": output_dir,
            }
        )
        out_dir = Path(output_dir)
        for name in ("ETaDaily", "ETrF", "LE", "H", "Rn", "G", "dT"):
            (out_dir / f"{name}_scene.tif").write_bytes(name.encode())
        return {
            "ET_daily": np.array([[1.0, np.nan, 3.0]]),
            "ETrF": np.array([[0.2, 0.4, np.nan]]),
        }

    def get_scene_quality(self):
        return {"quality": "GOOD", "status": "ACCEPTED"}


def make_registry_and_context(tmp_path, monkeypatch, pipeline=FakeMETRICPipeline):
    module = type("LandsatModule", (), {"METRICPipeline": pipeline})()
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "data_engine.landsat":
            return module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    settings = AgentSettings(workspace=tmp_path / "workspace")
    settings.workspace.mkdir(parents=True)
    store = Store(settings.workspace / "agent.db")
    registry = Registry()
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=[settings.workspace],
        settings=settings,
    )
    return registry, ctx


def test_rs_compute_et_runs_pipeline_and_returns_stats_and_artifacts(tmp_path, monkeypatch):
    registry, ctx = make_registry_and_context(tmp_path, monkeypatch)
    assert "rs_compute_et" in registry.names()

    scene = ctx.workspace_dir / "scene"
    scene.mkdir()
    result = registry.call(
        "rs_compute_et",
        {"landsat_dir": "scene", "output_dir": "runs/et", "config": {"x": 1}},
        ctx,
    )

    assert result.status == "ok", result.error
    assert result.value == {
        "ET_daily_mean": pytest.approx(2.0),
        "ET_daily_std": pytest.approx(1.0),
        "ETrF_mean": pytest.approx(0.3),
        "quality": "GOOD",
    }
    assert len(result.artifacts) == 7
    assert {Path(artifact.path).name.split("_", 1)[0] for artifact in result.artifacts} == {
        "ETaDaily",
        "ETrF",
        "LE",
        "H",
        "Rn",
        "G",
        "dT",
    }
    assert all(artifact.sha256 for artifact in result.artifacts)
    assert FakeMETRICPipeline.instances[-1].calls == [
        {
            "landsat_dir": str(scene),
            "meteo_data": [],
            "output_dir": str(ctx.workspace_dir / "runs" / "et"),
        }
    ]


def test_rs_compute_et_reports_missing_input(tmp_path, monkeypatch):
    registry, ctx = make_registry_and_context(tmp_path, monkeypatch)
    result = registry.call(
        "rs_compute_et",
        {"landsat_dir": "missing-scene", "output_dir": "runs/et"},
        ctx,
    )
    assert result.status == "failed"
    assert "missing-scene" in result.error


def test_rs_compute_et_names_missing_extra(tmp_path, monkeypatch):
    registry, ctx = make_registry_and_context(tmp_path, monkeypatch)
    scene = ctx.workspace_dir / "scene"
    scene.mkdir()
    real_import = builtins.__import__

    def missing_import(name, *args, **kwargs):
        if name == "data_engine.landsat":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_import)
    result = registry.call(
        "rs_compute_et",
        {"landsat_dir": "scene", "output_dir": "runs/et"},
        ctx,
    )
    assert result.status == "validation_error"
    assert "geoagent[rs]" in result.error
