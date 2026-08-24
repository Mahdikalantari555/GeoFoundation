"""Advisor tools: farm stress reports and recommendation evidence packs.

Farm registry convention (spec: advisor): farms live as a GeoJSON FeatureCollection;
each feature carries ``farm_id`` (+ optional crop, area_ha). Geometry is resolved
from ``farms_path`` or from a GeoMemory hit locator (facade cannot return raw
bytes yet — flagged as an upstream gap).

``geo_farm_report`` orchestrates existing tools (indices → reclassify → zonal
stats → polygonize → symbology) so every sub-step stays audited and cached.
``geo_recommend`` gathers stress state + expert-rule hits; the composing of
cited advice belongs to the agent loop.
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

DEFAULT_CLASS_RULES = [
    {"min": -1.0, "max": 0.4, "out": 2},
    {"min": 0.4, "max": 0.6, "out": 1},
    {"min": 0.6, "max": 1.0, "out": 0},
]
CLASS_LABELS = {0: "no stress", 1: "mild stress", 2: "severe stress"}
DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")
TOPIC_QUERIES = {
    "irrigation": "sugarcane irrigation scheduling water stress NDVI threshold",
    "fertilization": "sugarcane fertilization nutrient management stress",
    "spraying": "sugarcane pest disease spraying stress monitoring",
}


def _resolve(ctx: RunContext, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else ctx.workspace_dir / p


def _read_features(path: Path) -> list[dict[str, Any]]:
    fc = json.loads(path.read_text(encoding="utf-8"))
    return fc.get("features", [])


def _feature_bbox(geom: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for part in node.values():
                walk(part)
        elif isinstance(node, list):
            if node and isinstance(node[0], (int, float)):
                xs.append(float(node[0]))
                ys.append(float(node[1]))
            else:
                for part in node:
                    walk(part)

    walk(geom)
    return (min(xs), min(ys), max(xs), max(ys))


def _select_features(
    features: list[dict[str, Any]],
    farm_id: str | None,
    bbox: list[float] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if farm_id:
        exact = [f for f in features if f.get("properties", {}).get("farm_id") == farm_id]
        if exact:
            return exact, None
        fuzzy = [
            f
            for f in features
            if farm_id.lower() in str(f.get("properties", {}).get("farm_id", "")).lower()
        ]
        if fuzzy:
            return fuzzy, None
        return [], farm_id
    if bbox:
        w, s, e, n = bbox

        def intersects(f: dict[str, Any]) -> bool:
            fw, fs, fe, fn = _feature_bbox(f["geometry"])
            return not (fe < w or fw > e or fn < s or fs > n)

        selected = [f for f in features if intersects(f)]
        return selected[:50], None
    return [], None


def _parse_dates(paths: list[Path]) -> list[tuple[str, Path]]:
    dated: list[tuple[str, Path]] = []
    undated: list[Path] = []
    for p in paths:
        m = DATE_RE.search(p.stem)
        if m:
            dated.append((f"{m.group(1)}-{m.group(2)}-{m.group(3)}", p))
        else:
            undated.append(p)
    dated.sort()
    return dated


def _call(registry: Registry, ctx: RunContext, name: str, args: dict[str, Any]) -> ToolResult:
    return registry.call(name, args, ctx)


def _inner_ctx(ctx: RunContext) -> RunContext:
    """Derived context for orchestration sub-steps (many calls, long wall)."""
    import dataclasses

    return dataclasses.replace(
        ctx,
        max_tool_calls=500,
        deadline=time.monotonic() + 880.0,
    )


def _ingest_report(settings: Any, report_path: Path, collection: str) -> dict[str, Any]:
    try:
        from geoagent.tools.memory_tools import _get_memory

        memory = _get_memory(settings)
    except Exception as exc:  # noqa: BLE001 - memory is optional here
        return {"ingested": False, "reason": str(exc)[:200]}
    try:
        known = {c.name: c.id for c in memory.list_collections()}
        col_id = known.get(collection) or memory.create_collection(collection).id
        job = memory.ingest(str(report_path), col_id)
        return {"ingested": True, "asset_id": (job.result or {}).get("asset_id")}
    except Exception as exc:  # noqa: BLE001 - traceability is best-effort
        return {"ingested": False, "reason": str(exc)[:200]}


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="geo_farm_report",
            description=(
                "Build a stress report for one farm (farm_id) or all farms in a bbox "
                "over a set of dated multiband rasters. Produces report.md, stats.csv "
                "and a map.png of the latest classified date; thresholds are retrieved "
                "from the knowledge base and embedded as [S#] sources; the report is "
                "re-ingested into the 'reports' collection when GeoMemory is configured."
            ),
            params={
                "type": "object",
                "properties": {
                    "farm_id": {"type": "string"},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
                        "description": "[w,s,e,n] — alternative to farm_id",
                    },
                    "farms_path": {"type": "string"},
                    "raster_glob": {"type": "string", "description": "glob relative to workspace"},
                    "raster_paths": {"type": "array", "items": {"type": "string"}},
                    "indices": {"type": "array", "items": {"type": "string"}},
                    "band_map": {"type": "object"},
                    "class_rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "min": {"type": "number"},
                                "max": {"type": "number"},
                                "out": {"type": "integer"},
                            },
                            "required": ["min", "max", "out"],
                        },
                        "description": "default NDVI stress rules used when omitted",
                    },
                    "out_dir": {"type": "string"},
                },
                "required": ["farms_path", "raster_glob"],
                "additionalProperties": False,
            },
            returns="report/stats/map paths, per-date means, sources",
            timeout_s=900.0,
            cacheable=True,
        )
    )
    def geo_farm_report(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        settings = ctx.settings
        farm_id = args.get("farm_id")
        bbox = args.get("bbox")
        if bool(farm_id) == bool(bbox):
            return ToolResult(status="validation_error", error="provide exactly one of farm_id or bbox")

        farms_path = _resolve(ctx, args["farms_path"])
        if not farms_path.exists():
            return ToolResult(status="validation_error", error=f"farms file not found: {args['farms_path']}")
        features = _read_features(farms_path)
        selected, wanted = _select_features(features, farm_id, bbox)
        if not selected:
            ids = sorted({str(f.get("properties", {}).get("farm_id")) for f in features})
            hint = f"known ids: {ids[:10]}" if wanted else "no farms intersect bbox"
            return ToolResult(status="validation_error", error=f"farm not found ({wanted}); {hint}")

        paths = [_resolve(ctx, p) for p in args.get("raster_paths") or []]
        pattern = args.get("raster_glob")
        if pattern:
            paths.extend(Path(p) for p in sorted(ctx.workspace_dir.glob(pattern)))
        paths = [p for p in paths if p.is_file()]
        if not paths:
            return ToolResult(status="validation_error", error="no raster files matched")
        dated = _parse_dates(paths)
        if not dated:
            return ToolResult(
                status="validation_error",
                error="no dates found in file names (expected YYYY-MM-DD or YYYYMMDD)",
            )

        indices = [i.upper() for i in (args.get("indices") or ["NDVI"])]
        primary = indices[0]
        band_map = args.get("band_map")
        class_rules = args.get("class_rules") or DEFAULT_CLASS_RULES
        slug = (farm_id or f"bbox{len(selected)}").replace("/", "_")

        # Threshold evidence from the knowledge base.
        src_res = _call(
            registry,
            _inner_ctx(ctx),
            "geo_search",
            {"query": f"sugarcane {primary} stress severity threshold", "top_k": 5},
        )
        sources: list[dict[str, Any]] = []
        if src_res.status == "ok":
            for i, hit in enumerate(src_res.value["hits"], start=1):
                sources.append({"key": f"S{i}", "text": hit["text"][:300], "locator": hit["locator"]})

        out_dir = _resolve(ctx, args.get("out_dir") or f"runs/reports/{slug}")
        inner_ctx = _inner_ctx(ctx)
        out_dir.mkdir(parents=True, exist_ok=True)

        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        latest_classes_tif: Path | None = None
        for date, raster_path in dated:
            idx = _call(
                registry,
                inner_ctx,
                "geo_compute_indices",
                {
                    "input_tif": str(raster_path),
                    "indices": indices,
                    "output_dir": str(out_dir / "indices"),
                    **({"band_map": band_map} if band_map else {}),
                },
            )
            if idx.status != "ok":
                warnings.append(f"{date}: indices failed ({idx.error})")
                continue
            index_tif = idx.value["indices"][primary]["tif"]

            cls = _call(
                registry,
                inner_ctx,
                "geo_reclassify",
                {
                    "input_tif": index_tif,
                    "rules": class_rules,
                    "output_tif": str(out_dir / f"classes_{date}.tif"),
                },
            )
            if cls.status != "ok":
                warnings.append(f"{date}: reclassify failed ({cls.error})")
                continue
            latest_classes_tif = out_dir / f"classes_{date}.tif"

            farm_fc = {"type": "FeatureCollection", "features": selected}
            farm_file = out_dir / f"aoi_{date}.geojson"
            farm_file.write_text(json.dumps(farm_fc), encoding="utf-8")
            zone = _call(
                registry,
                inner_ctx,
                "geo_zonal_stats",
                {
                    "raster_tif": index_tif,
                    "polygons_geojson": str(farm_file.relative_to(ctx.workspace_dir)),
                    "id_field": "farm_id",
                    "out_csv": str(out_dir / f"zonal_{date}.csv"),
                },
            )
            mean_val = None
            if zone.status == "ok":
                csv_path = out_dir / f"zonal_{date}.csv"
                with open(csv_path, newline="", encoding="utf-8") as fh:
                    rrows = list(csv.DictReader(fh))
                if rrows and "mean" in rrows[0]:
                    try:
                        mean_val = float(rrows[0]["mean"])
                    except ValueError:
                        mean_val = None
            else:
                warnings.append(f"{date}: zonal failed ({zone.error})")

            def classify(v: float) -> int:
                for rule in class_rules:
                    if rule["min"] <= v < rule["max"]:
                        return int(rule["out"])
                return max(int(r["out"]) for r in class_rules)

            rows.append({
                "date": date,
                "raster": str(raster_path),
                f"mean_{primary.lower()}": round(mean_val, 4) if mean_val is not None else None,
                "stress_class": classify(mean_val) if mean_val is not None else None,
            })

        if not rows:
            return ToolResult(status="failed", error="no usable dates; " + "; ".join(warnings[:3]))

        # Map of the latest classified date.
        map_png: str | None = None
        if latest_classes_tif is not None:
            pol = _call(
                registry,
                inner_ctx,
                "geo_polygonize",
                {"input_tif": str(latest_classes_tif), "output_geojson": str(out_dir / "latest_classes.geojson")},
            )
            if pol.status == "ok":
                sym = _call(
                    registry,
                    ctx,
                    "geo_symbology",
                    {
                        "input_geojson": str(out_dir / "latest_classes.geojson"),
                        "field": "class",
                        "classification": {"scheme": "manual", "breaks": [-0.5, 0.5, 1.5]},
                        "palette": ["#1a9850", "#fee08b", "#d73027"],
                        "out_png": str(out_dir / "map.png"),
                    },
                )
                if sym.status == "ok":
                    map_png = str(out_dir / "map.png")

        stats_csv = out_dir / "stats.csv"
        fieldnames = ["date", "raster", f"mean_{primary.lower()}", "stress_class"]
        with open(stats_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        titled_rows = [
            {**r, "stress_label": CLASS_LABELS.get(r["stress_class"], "?") if r["stress_class"] is not None else "?"}
            for r in rows
        ]
        valid_means = [r[f"mean_{primary.lower()}"] for r in rows if r[f"mean_{primary.lower()}"] is not None]
        worst = min(rows, key=lambda r: r[f"mean_{primary.lower()}"] or 9e9)
        lines = [
            f"# Stress report — {farm_id or 'bbox selection'}",
            "",
            f"- Product index: {primary}",
            f"- Window: {rows[0]['date']} → {rows[-1]['date']} ({len(rows)} dates)",
            f"- Mean {primary}: {min(valid_means):.3f} … {max(valid_means):.3f}"
            if valid_means else f"- Mean {primary}: n/a",
            f"- Worst date: {worst['date']} ({CLASS_LABELS.get(worst['stress_class'], '?')})",
            "",
            "| date | mean | class |",
            "|---|---|---|",
        ]
        lines += [
            f"| {r['date']} | {r[f'mean_{primary.lower()}']} | {r['stress_label']} |"
            for r in titled_rows
        ]
        if sources:
            lines += ["", "## Sources"]
            lines += [f"- [{s['key']}] {s['text']} ({s['locator'].get('file', '')})" for s in sources]
        if warnings:
            lines += ["", "## Warnings"] + [f"- {w}" for w in warnings]
        report_md = out_dir / "report.md"
        report_md.write_text("\n".join(lines), encoding="utf-8")

        ingest_info = (
            _ingest_report(settings, report_md, "reports") if settings is not None else {"ingested": False}
        )

        return ToolResult(
            status="ok",
            value={
                "farm_id": farm_id,
                "report_md": str(report_md),
                "stats_csv": str(stats_csv),
                "map_png": map_png,
                "dates": [r["date"] for r in rows],
                "trend": {
                    "first": rows[0][f"mean_{primary.lower()}"],
                    "last": rows[-1][f"mean_{primary.lower()}"],
                    "worst_date": worst["date"],
                },
                "sources": sources,
                "warnings": warnings,
                "memory_ingest": ingest_info,
            },
            artifacts=[
                ArtifactRef(path=str(report_md)),
                ArtifactRef(path=str(stats_csv)),
                *([ArtifactRef(path=map_png)] if map_png else []),
            ],
        )

    @registry.register(
        ToolDefinition(
            name="geo_recommend",
            description=(
                "Gather an evidence pack for irrigation/fertilization/spraying advice: "
                "latest stress state (from a report stats.csv, a report.md artifact dir, "
                "or an explicit ndvi_mean) plus expert-rule hits from the knowledge "
                "base returned as 'hits' ([S#]-citable). Compose the actual advice in "
                "your answer text citing these keys; abstain if gaps are reported."
            ),
            params={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "enum": ["irrigation", "fertilization", "spraying"]},
                    "farm_id": {"type": "string"},
                    "report_dir": {"type": "string", "description": "a geo_farm_report out_dir"},
                    "ndvi_mean": {"type": "number"},
                    "knowledge_query": {"type": "string"},
                    "farms_path": {"type": "string"},
                },
                "required": ["topic", "farm_id"],
                "additionalProperties": False,
            },
            returns="stress state + citable rule hits + gaps",
            timeout_s=180.0,
            cacheable=False,
        )
    )
    def geo_recommend(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        topic: str = args["topic"]
        gaps: list[str] = []
        state: dict[str, Any] = {}

        report_dir = args.get("report_dir")
        if report_dir:
            csv_path = _resolve(ctx, f"{report_dir.rstrip('/')}/stats.csv")
            if csv_path.exists():
                with open(csv_path, newline="", encoding="utf-8") as fh:
                    rows = list(csv.DictReader(fh))
                if rows:
                    last = rows[-1]
                    mean_key = next((k for k in last if k.startswith("mean_")), None)
                    klass_raw = last.get("stress_class")
                    try:
                        label = CLASS_LABELS.get(int(klass_raw)) if klass_raw not in (None, "") else None
                    except (TypeError, ValueError):
                        label = None
                    state = {
                        "date": last.get("date"),
                        "mean": last.get(mean_key) if mean_key else None,
                        "stress_class": klass_raw,
                        "stress_label": label,
                    }
                else:
                    gaps.append(f"stats.csv at {csv_path} has no rows")
            else:
                gaps.append(f"no stats.csv under {report_dir}")
        elif args.get("ndvi_mean") is not None:
            v = float(args["ndvi_mean"])
            rules = DEFAULT_CLASS_RULES
            klass = next((int(r["out"]) for r in rules if r["min"] <= v < r["max"]), None)
            state = {"mean": round(v, 4), "stress_class": klass, "stress_label": CLASS_LABELS.get(klass)}
        else:
            gaps.append("provide report_dir or ndvi_mean for current stress state")

        query = args.get("knowledge_query") or TOPIC_QUERIES[topic]
        search = _call(registry, _inner_ctx(ctx), "geo_search", {"query": query, "top_k": 5})
        hits: list[dict[str, Any]] = []
        if search.status == "ok":
            for hit in search.value["hits"]:
                hits.append({"id": hit["id"], "text": hit["text"], "locator": hit["locator"], "score": hit["score"]})
        else:
            gaps.append(f"knowledge search failed: {search.error}")
        if not hits:
            gaps.append("no expert rules found for topic — ingest agronomy sources first")

        return ToolResult(
            status="ok",
            value={
                "topic": topic,
                "farm_id": args["farm_id"],
                "stress_state": state,
                "hits": hits,
                "gaps": gaps,
                "note": "cite [S1..Sn] mapped to hits; treat gaps as abstention triggers",
            },
        )
