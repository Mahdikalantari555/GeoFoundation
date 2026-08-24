"""Memory tools wrapping the GeoMemory public facade only.

Invariant: `import geomemory` root exports exclusively; never GeoMemory's DB.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext, ToolDefinition, ToolResult

_MEMORY: Any = None
_SETTINGS_REF: AgentSettings | None = None

MAX_HIT_CHARS = 1200


def _get_memory(settings: AgentSettings) -> Any:
    global _MEMORY, _SETTINGS_REF
    if _MEMORY is None or _SETTINGS_REF is not settings:
        try:
            geomemory = importlib.import_module("geomemory")
        except ImportError as exc:
            raise RuntimeError(
                "geomemory is not installed. Install it (pip install -e ../GeoMemory) "
                "and set memory_workspace in agent.yaml."
            ) from exc
        if not settings.memory_workspace:
            raise RuntimeError(
                "memory_workspace is not set in agent.yaml — point it at an existing "
                "GeoMemory workspace or create one with `geomemory init`."
            )
        _MEMORY = geomemory.GeoMemory.open(settings.memory_workspace)
        _SETTINGS_REF = settings
    return _MEMORY


def _resolve_collection(memory: Any, name: str) -> str:
    for col in memory.list_collections():
        if col.name == name:
            return col.id
    return memory.create_collection(name).id


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="geo_ingest",
            description=(
                "Ingest a local file (PDF/MD/TXT/CSV/PY/GeoJSON/GeoTIFF) into a named "
                "GeoMemory collection. Duplicate content short-circuits as skipped."
            ),
            params={
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "description": "path to the source file"},
                    "collection": {"type": "string", "description": "collection name"},
                },
                "required": ["source_path", "collection"],
                "additionalProperties": False,
            },
            returns="asset_id, revision_id, segment_count (or skipped duplicate info)",
            timeout_s=300.0,
        )
    )
    def geo_ingest(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        settings: AgentSettings = ctx.settings  # type: ignore[attr-defined]
        memory = _get_memory(settings)
        src = Path(args["source_path"])
        src = src if src.is_absolute() else ctx.workspace_dir / src
        collection_id = _resolve_collection(memory, args["collection"])
        job = memory.ingest(str(src), collection_id)
        value = dict(job.result or {})
        value["collection"] = args["collection"]
        return ToolResult(status="ok", value=value)

    @registry.register(
        ToolDefinition(
            name="geo_search",
            description=(
                "Hybrid (sparse+dense) search over the GeoMemory knowledge base. "
                "bbox is [west, south, east, north] WGS84 lon/lat."
            ),
            params={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 50},
                    "collections": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "restrict to collection names",
                    },
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 4,
                        "maxItems": 4,
                        "description": "[w, s, e, n] lon/lat",
                    },
                    "date_range": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "[from ISO date, to ISO date]",
                    },
                    "sensors": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            returns="hits with id/score/text/locator/metadata; empty hits means no evidence",
            cacheable=False,
        )
    )
    def geo_search(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        settings: AgentSettings = ctx.settings  # type: ignore[attr-defined]
        memory = _get_memory(settings)
        from geomemory import SpatialFilter, TemporalFilter

        collections = args.get("collections")
        collection_ids = None
        if collections:
            known = {c.name: c.id for c in memory.list_collections()}
            collection_ids = [known[name] for name in collections if name in known]
        spatial = SpatialFilter(bbox=tuple(args["bbox"])) if args.get("bbox") else None
        temporal = (
            TemporalFilter(from_=args["date_range"][0], to=args["date_range"][1])
            if args.get("date_range")
            else None
        )
        result = memory.search(
            args["query"],
            top_k=int(args.get("top_k") or 5),
            collections=collection_ids,
            spatial=spatial,
            temporal=temporal,
            sensor=args.get("sensors"),
        )
        hits = []
        for hit in result.hits:
            text = hit.text[:MAX_HIT_CHARS]
            hits.append(
                {
                    "id": hit.id,
                    "score": round(hit.score, 4),
                    "text": text,
                    "locator": hit.locator,
                    "metadata": hit.metadata,
                }
            )
        return ToolResult(status="ok", value={"hits": hits, "total_hits": len(hits)})

    @registry.register(
        ToolDefinition(
            name="geo_list_collections",
            description="List GeoMemory collections (id, name, description).",
            params={"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    def geo_list_collections(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        settings: AgentSettings = ctx.settings  # type: ignore[attr-defined]
        memory = _get_memory(settings)
        cols = [
            {"id": c.id, "name": c.name, "description": c.description}
            for c in memory.list_collections()
        ]
        return ToolResult(status="ok", value={"collections": cols})

    @registry.register(
        ToolDefinition(
            name="geo_create_collection",
            description="Create a GeoMemory collection.",
            params={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        )
    )
    def geo_create_collection(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        settings: AgentSettings = ctx.settings  # type: ignore[attr-defined]
        memory = _get_memory(settings)
        col = memory.create_collection(args["name"], args.get("description", ""))
        return ToolResult(status="ok", value={"id": col.id, "name": col.name})
