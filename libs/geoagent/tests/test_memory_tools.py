import pytest

pytest.importorskip("geomemory")

from geomemory import GeoMemory

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import memory_tools


@pytest.fixture()
def gm_workspace(tmp_path):
    ws = tmp_path / "gm"
    memory = GeoMemory.create(ws)
    yield ws
    memory.close()


def make_ctx(tmp_path, settings):
    store = Store(tmp_path / "agent.db")
    return RunContext(
        store=store,
        workspace_dir=tmp_path,
        sandbox_roots=[tmp_path],
        settings=settings,
    )


def test_ingest_then_search(tmp_path, gm_workspace):
    settings = AgentSettings(workspace=tmp_path / "ws", memory_workspace=str(gm_workspace))
    (tmp_path / "ws").mkdir(exist_ok=True)

    doc = tmp_path / "note.md"
    doc.write_text(
        "# Sugarcane stress\n\nWater stress reduces NDVI below 0.4 in severe cases.\n",
        encoding="utf-8",
    )

    registry = Registry()
    memory_tools.register(registry)
    ctx = make_ctx(tmp_path, settings)

    res = registry.call("geo_ingest", {"source_path": str(doc), "collection": "papers"}, ctx)
    assert res.status == "ok"
    assert res.value["segment_count"] >= 1

    dup = registry.call("geo_ingest", {"source_path": str(doc), "collection": "papers"}, ctx)
    assert dup.status == "ok"
    assert dup.value.get("skipped") is True

    found = registry.call("geo_search", {"query": "NDVI water stress"}, ctx)
    assert found.status == "ok"
    assert len(found.value["hits"]) >= 1


def test_collections_roundtrip(tmp_path, gm_workspace):
    settings = AgentSettings(workspace=tmp_path / "ws2", memory_workspace=str(gm_workspace))
    (tmp_path / "ws2").mkdir(exist_ok=True)
    registry = Registry()
    memory_tools.register(registry)
    ctx = make_ctx(tmp_path, settings)

    created = registry.call(
        "geo_create_collection", {"name": "reports", "description": "generated reports"}, ctx
    )
    assert created.status == "ok"
    listed = registry.call("geo_list_collections", {}, ctx)
    names = [c["name"] for c in listed.value["collections"]]
    assert "reports" in names


def test_missing_memory_config_is_actionable(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws3", memory_workspace=None)
    (tmp_path / "ws3").mkdir(exist_ok=True)
    registry = Registry()
    memory_tools.register(registry)
    ctx = make_ctx(tmp_path, settings)
    res = registry.call("geo_list_collections", {}, ctx)
    assert res.status == "failed"
    assert "memory_workspace" in res.error or "geomemory" in res.error
