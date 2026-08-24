"""GIS tools integration tests — synthetic raster/polygons, real rasterio."""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

pytest.importorskip("rasterio")

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import gis_tools


@pytest.fixture()
def env(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    (tmp_path / "ws").mkdir(parents=True)
    store = Store(settings.workspace / "agent.db")
    registry = Registry()
    gis_tools.register(registry)
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(),
        settings=settings,
    )
    return ctx, registry, tmp_path / "ws"


def make_tif(path, bands: dict[int, np.ndarray]):
    profile = {
        "driver": "GTiff",
        "height": bands[1].shape[0],
        "width": bands[1].shape[1],
        "count": len(bands),
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(48.3, 31.6, 0.01, 0.01),
        "nodata": -9999.0,
    }
    with rasterio.open(path, "w", **profile) as dst:
        for idx in sorted(bands):
            dst.write(bands[idx].astype("float32"), idx)


def test_compute_indices_reclassify_polygonize_chain(env):
    ctx, reg, ws = env
    rng = np.random.default_rng(42)
    tif = ws / "scene.tif"
    make_tif(
        tif,
        {1: rng.uniform(0, 2000, (32, 32)), 2: rng.uniform(0, 2000, (32, 32)),
         3: rng.uniform(0, 4000, (32, 32)), 4: rng.uniform(0, 8000, (32, 32))},
    )
    res = reg.call(
        "geo_compute_indices",
        {"input_tif": "scene.tif", "indices": ["NDVI", "NDWI"], "band_map": {"blue": 1, "green": 2, "red": 3, "nir": 4}},
        ctx,
    )
    assert res.status == "ok", res.error
    assert set(res.value["indices"]) == {"NDVI", "NDWI"}
    assert res.value["indices"]["NDVI"]["stats"]["count"] > 0

    rec = reg.call(
        "geo_reclassify",
        {
            "input_tif": str(res.value["indices"]["NDVI"]["tif"]),
            "rules": [
                {"min": -1, "max": 0.5, "out": 2},
                {"min": 0.5, "max": 1, "out": 0},
            ],
            "output_tif": "classes.tif",
        },
        ctx,
    )
    assert rec.status == "ok", rec.error
    assert set(rec.value["histogram"]) <= {"0", "2"}

    poly = reg.call(
        "geo_polygonize", {"input_tif": "classes.tif", "output_geojson": "classes.geojson"}, ctx
    )
    assert poly.status == "ok", poly.error
    assert poly.value["feature_count"] >= 1
    fc = json.loads((ws / "classes.geojson").read_text())
    assert fc["type"] == "FeatureCollection"
    assert all(f["properties"]["class"] in (0, 2) for f in fc["features"])


def test_reclassify_overlap_rejected(env):
    ctx, reg, ws = env
    tif = ws / "tiny.tif"
    make_tif(tif, {1: np.full((4, 4), 0.7)})
    res = reg.call(
        "geo_reclassify",
        {
            "input_tif": "tiny.tif",
            "rules": [{"min": 0, "max": 0.8, "out": 1}, {"min": 0.6, "max": 1, "out": 2}],
            "output_tif": "bad.tif",
        },
        ctx,
    )
    assert res.status == "validation_error"
    assert "overlap" in res.error


def test_zonal_stats(env):
    ctx, reg, ws = env
    rng = np.random.default_rng(7)
    tif = ws / "z.tif"
    make_tif(tif, {1: rng.uniform(0.2, 0.9, (16, 16))})
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"farm_id": "f1"},
             "geometry": {"type": "Polygon", "coordinates": [[[48.30, 31.59], [48.34, 31.59], [48.34, 31.55], [48.30, 31.55], [48.30, 31.59]]]}},
            {"type": "Feature", "properties": {"farm_id": "f2"},
             "geometry": {"type": "Polygon", "coordinates": [[[48.35, 31.60], [48.38, 31.60], [48.38, 31.57], [48.35, 31.57], [48.35, 31.60]]]}},
        ],
    }
    (ws / "farms.geojson").write_text(json.dumps(fc))
    res = reg.call(
        "geo_zonal_stats",
        {"raster_tif": "z.tif", "polygons_geojson": "farms.geojson", "id_field": "farm_id", "out_csv": "zones.csv"},
        ctx,
    )
    assert res.status == "ok", res.error
    assert res.value["row_count"] == 2
    assert (ws / "zones.csv").exists()


def test_symbology_png(env):
    ctx, reg, ws = env
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"stress": v},
             "geometry": {"type": "Polygon",
                          "coordinates": [[[48.30 + 0.01 * i, 31.55], [48.33 + 0.01 * i, 31.55],
                                           [48.33 + 0.01 * i, 31.52], [48.30 + 0.01 * i, 31.52],
                                           [48.30 + 0.01 * i, 31.55]]]}}
            for i, v in enumerate([0.15, 0.45, 0.75])
        ],
    }
    (ws / "stress.geojson").write_text(json.dumps(fc))
    res = reg.call(
        "geo_symbology",
        {
            "input_geojson": "stress.geojson",
            "field": "stress",
            "classification": {"scheme": "quantiles", "n_classes": 3},
            "out_png": "stress.png",
        },
        ctx,
    )
    assert res.status == "ok", res.error
    assert len(res.value["classes"]) == 3
    assert sum(c["features"] for c in res.value["classes"]) == 3
    assert (ws / "stress.png").stat().st_size > 1000


def test_missing_dep_error_names_extra(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "rasterio":
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    settings = AgentSettings(workspace=tmp_path / "ws4")
    (tmp_path / "ws4").mkdir(parents=True)
    store = Store(settings.workspace / "agent.db")
    registry = Registry()
    gis_tools.register(registry)
    ctx = RunContext(store=store, workspace_dir=settings.workspace,
                     sandbox_roots=[settings.workspace], settings=settings)
    res = registry.call("geo_reclassify", {
        "input_tif": "x.tif", "rules": [{"min": 0, "max": 1, "out": 1}], "output_tif": "y.tif"
    }, ctx)
    assert res.status == "failed"
    assert "geoagent[rs]" in res.error
