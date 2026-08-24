"""Advisor tools tests: farm report orchestration + recommendation evidence."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

pytest.importorskip("rasterio")

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import advisor_tools, gis_tools


def make_scene(path: Path, nir_mean: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(abs(hash(str(nir_mean))) % 2**16)
    red = rng.uniform(800, 1200, (16, 16))
    nir = rng.uniform(max(0.0, nir_mean - 300), nir_mean + 300, (16, 16))
    with rasterio.open(
        str(path), "w", driver="GTiff", height=16, width=16, count=4,
        dtype="float32", crs="EPSG:4326",
        transform=from_origin(48.3, 31.6, 0.01, 0.01), nodata=-9999.0,
    ) as dst:
        dst.write(np.zeros((16, 16), dtype="float32"), 1)
        dst.write(np.zeros((16, 16), dtype="float32"), 2)
        dst.write(red.astype("float32"), 3)
        dst.write(nir.astype("float32"), 4)


def make_farms(path: Path) -> None:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"farm_id": "farm-12", "crop": "sugarcane"},
             "geometry": {"type": "Polygon", "coordinates": [
                 [[48.30, 31.59], [48.38, 31.59], [48.38, 31.51], [48.30, 31.51], [48.30, 31.59]]]}},
            {"type": "Feature",
             "properties": {"farm_id": "farm-13", "crop": "sugarcane"},
             "geometry": {"type": "Polygon", "coordinates": [
                 [[48.40, 31.59], [48.45, 31.59], [48.45, 31.55], [48.40, 31.55], [48.40, 31.59]]]}},
        ],
    }
    path.write_text(json.dumps(fc), encoding="utf-8")


@pytest.fixture()
def env(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    ws = settings.workspace
    ws.mkdir(parents=True)
    store = Store(ws / "agent.db")
    registry = Registry()
    gis_tools.register(registry)
    advisor_tools.register(registry)
    ctx = RunContext(store=store, workspace_dir=ws,
                     sandbox_roots=[ws], settings=settings)

    make_farms(ws / "farms.geojson")
    make_scene(ws / "scenes" / "s2_2025-07-01.tif", nir_mean=2600)
    make_scene(ws / "scenes" / "s2_2025-07-15.tif", nir_mean=1400)
    return settings, registry, ctx, ws


def test_report_full_chain(env):
    _settings, reg, ctx, ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "farm-12",
        "farms_path": "farms.geojson",
        "raster_glob": "scenes/*.tif",
        "band_map": {"green": 1, "red": 3, "nir": 4},
        "out_dir": "runs/reports/farm-12",
    }, ctx)
    assert res.status == "ok", res.error
    val = res.value
    assert len(val["dates"]) == 2
    assert val["trend"]["last"] < val["trend"]["first"]
    assert val["map_png"] and (ws / "runs/reports/farm-12/map.png").exists()
    assert (ws / "runs/reports/farm-12/report.md").exists()
    assert (ws / "runs/reports/farm-12/stats.csv").exists()

    md = (ws / "runs/reports/farm-12/report.md").read_text(encoding="utf-8")
    assert "| date | mean | class |" in md
    assert "2025-07-01" in md and "2025-07-15" in md
    # memory not configured → traceability skipped gracefully
    assert val["memory_ingest"]["ingested"] is False


def test_report_unknown_farm_lists_ids(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "nope", "farms_path": "farms.geojson", "raster_glob": "scenes/*.tif"
    }, ctx)
    assert res.status == "validation_error"
    assert "farm-12" in res.error and "farm-13" in res.error


def test_report_requires_exclusive_selector(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "farm-12", "bbox": [48, 31, 49, 32],
        "farms_path": "farms.geojson", "raster_glob": "scenes/*.tif"
    }, ctx)
    assert res.status == "validation_error"


def test_bbox_mode_selects_intersecting(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "bbox": [48.41, 31.56, 48.44, 31.58],
        "farms_path": "farms.geojson",
        "raster_glob": "scenes/*.tif",
        "band_map": {"green": 1, "red": 3, "nir": 4},
        "out_dir": "runs/reports/bboxsel",
    }, ctx)
    assert res.status == "ok", res.error
    assert res.value["farm_id"] is None


def test_recommend_evidence_pack_from_ndvi(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_recommend", {
        "topic": "irrigation", "farm_id": "farm-12", "ndvi_mean": 0.31,
        "knowledge_query": "water stress irrigation",
    }, ctx)
    assert res.status == "ok", res.error
    val = res.value
    assert val["stress_state"]["stress_label"] == "severe stress"
    assert isinstance(val["hits"], list)
    assert any("knowledge search failed" in g for g in val["gaps"]) or val["hits"]


def test_recommend_gaps_without_evidence(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_recommend", {"topic": "spraying", "farm_id": "farm-12"}, ctx)
    assert res.status == "ok"
    assert any("report_dir or ndvi_mean" in g for g in res.value["gaps"])
