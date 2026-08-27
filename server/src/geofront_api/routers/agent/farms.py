"""Farms registry + stress report endpoints (M6 Geo)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...errors import GeoFrontError
from ...jobs import get_job_manager
from ...services.agent import get_agent_service
from ...state import get_state

router = APIRouter(prefix="/agent/farms", tags=["agent"])

# ── helpers ──────────────────────────────────────────────────────────────────

CLASS_LABELS = {0: "no stress", 1: "mild stress", 2: "severe stress"}


def _workspace_roots() -> list[Path]:
    roots: list[Path] = []
    state = get_state()
    if state.workspace_path is not None:
        roots.append(Path(state.workspace_path))
    try:
        svc = get_agent_service()
        if svc.is_initialized:
            roots.append(Path(svc._settings.workspace))
            # also include parent (main workspace) sibling runs/
            roots.append(Path(svc._settings.workspace).parent)
    except Exception:
        pass
    # dedupe preserving order
    seen: set[str] = set()
    uniq: list[Path] = []
    for r in roots:
        s = str(r.resolve()) if r.exists() else str(r)
        if s not in seen:
            seen.add(s)
            uniq.append(r)
    return uniq


def _find_farms_geojson() -> tuple[Path | None, list[dict[str, Any]]]:
    candidates: list[Path] = []
    for root in _workspace_roots():
        if not root.exists():
            continue
        # common names first
        for pat in ("farms.geojson", "**/farms.geojson", "**/*farm*.geojson", "**/*.geojson"):
            candidates.extend(sorted(root.glob(pat)))
    # prefer shortest path with farm_id features
    best: tuple[Path, list[dict[str, Any]]] | None = None
    for cand in candidates:
        if not cand.is_file():
            continue
        try:
            fc = json.loads(cand.read_text(encoding="utf-8"))
            feats = fc.get("features", []) if isinstance(fc, dict) else []
            if feats and any("farm_id" in (f.get("properties") or {}) for f in feats):
                # prefer farm-named files
                score = 0 if "farm" in cand.name.lower() else 1
                if best is None or score < 0:
                    best = (cand, feats)
                    if score == 0 and len(feats) > 0:
                        return cand, feats
        except Exception:
            continue
    if best is not None:
        return best
    return None, []


def _feature_bbox(geom: dict[str, Any]) -> list[float] | None:
    xs: list[float] = []
    ys: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            if node and isinstance(node[0], (int, float)):
                try:
                    xs.append(float(node[0]))
                    ys.append(float(node[1]))
                except Exception:
                    pass
            else:
                for part in node:
                    walk(part)

    try:
        walk(geom)
        if xs and ys:
            return [min(xs), min(ys), max(xs), max(ys)]
    except Exception:
        pass
    return None


def _report_dirs() -> list[Path]:
    dirs: list[Path] = []
    for root in _workspace_roots():
        for pat in ("runs/reports/*", "geoagent/runs/reports/*", "runs/reports/**/*"):
            for p in root.glob(pat):
                if p.is_dir() and ((p / "stats.csv").exists() or (p / "report.md").exists()):
                    dirs.append(p)
        # also direct run reports under agent workspace
        agent_rep = root / "runs" / "reports"
        if agent_rep.is_dir():
            for sub in agent_rep.iterdir():
                if sub.is_dir() and sub not in dirs:
                    if ((sub / "stats.csv").exists() or (sub / "report.md").exists()):
                        dirs.append(sub)
    # dedupe
    uniq: dict[str, Path] = {}
    for d in dirs:
        uniq[str(d.resolve())] = d
    return sorted(uniq.values())


def _parse_stats(stats_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with open(stats_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                # normalize
                norm: dict[str, Any] = dict(r)
                # coerce numeric
                for k in ("mean_ndvi", "mean", "mean_evi", "stress_class"):
                    if k in norm and norm[k] not in (None, ""):
                        try:
                            norm[k] = float(norm[k]) if "mean" in k else int(float(norm[k]))
                        except Exception:
                            pass
                # ensure stress_label
                sc = norm.get("stress_class")
                if sc is not None:
                    try:
                        norm["stress_label"] = CLASS_LABELS.get(int(sc), "?")
                    except Exception:
                        norm["stress_label"] = "?"
                rows.append(norm)
    except Exception:
        pass
    return rows


def _resolve_report_dir(farm_id: str) -> Path | None:
    # exact slug match first
    slug = farm_id.replace("/", "_")
    for d in _report_dirs():
        if d.name == slug or d.name == farm_id:
            return d
        # also check stats.csv farm_id inside?
    # fallback: any report whose stats.csv contains farm_id column
    # not doing exhaustive; return None
    return None


# ── models ───────────────────────────────────────────────────────────────────


class FarmReportRequest(BaseModel):
    farms_path: str | None = None
    raster_glob: str | None = None
    raster_paths: list[str] | None = None
    indices: list[str] | None = None
    out_dir: str | None = None


# ── routes ───────────────────────────────────────────────────────────────────


@router.get("")
async def list_farms() -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    farms_path, features = _find_farms_geojson()
    reports = _report_dirs()

    # map report dir name -> path
    report_index: dict[str, str] = {p.name: str(p) for p in reports}

    farms: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties") or {}
        fid = str(props.get("farm_id", ""))
        if not fid:
            continue
        slug = fid.replace("/", "_")
        farms.append(
            {
                "farm_id": fid,
                "properties": props,
                "bbox": _feature_bbox(f.get("geometry") or {}),
                "has_report": slug in report_index or fid in report_index,
                "report_dir": report_index.get(slug) or report_index.get(fid),
            }
        )

    return {
        "farms": farms,
        "count": len(farms),
        "source": str(farms_path) if farms_path else None,
        "reports": [{"dir": str(p), "name": p.name} for p in reports],
    }


@router.get("/{farm_id}")
async def get_farm(farm_id: str) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    _, features = _find_farms_geojson()
    match = next((f for f in features if str((f.get("properties") or {}).get("farm_id")) == farm_id), None)
    if match is None:
        # fuzzy
        match = next(
            (f for f in features if farm_id.lower() in str((f.get("properties") or {}).get("farm_id", "")).lower()),
            None,
        )
    if match is None:
        raise GeoFrontError(code="farm_not_found", message=f"Farm not found: {farm_id}", status_code=404)

    slug = farm_id.replace("/", "_")
    rdir = _resolve_report_dir(farm_id)
    if rdir is None:
        for p in _report_dirs():
            if p.name == slug:
                rdir = p
                break

    report_summary: dict[str, Any] | None = None
    if rdir is not None:
        stats = _parse_stats(rdir / "stats.csv")
        report_md = None
        md_path = rdir / "report.md"
        if md_path.exists():
            try:
                report_md = md_path.read_text(encoding="utf-8")[:20000]
            except Exception:
                report_md = None
        map_png = rdir / "map.png"
        report_summary = {
            "dir": str(rdir),
            "has_report_md": (rdir / "report.md").exists(),
            "has_stats_csv": (rdir / "stats.csv").exists(),
            "has_map_png": map_png.exists(),
            "map_png": str(map_png) if map_png.exists() else None,
            "stats": stats,
            "report_md": report_md,
        }

    return {
        "farm": {
            "farm_id": farm_id,
            "properties": match.get("properties") or {},
            "geometry": match.get("geometry"),
            "bbox": _feature_bbox(match.get("geometry") or {}),
        },
        "report": report_summary,
    }


@router.get("/{farm_id}/report")
async def get_farm_report(farm_id: str) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    slug = farm_id.replace("/", "_")
    candidates = [p for p in _report_dirs() if p.name == slug or p.name == farm_id]
    # also resolve via helper
    if not candidates:
        rdir = _resolve_report_dir(farm_id)
        if rdir is not None:
            candidates = [rdir]

    if not candidates:
        raise GeoFrontError(code="report_not_found", message=f"No report for farm {farm_id}", status_code=404)

    rdir = candidates[0]
    stats = _parse_stats(rdir / "stats.csv")
    report_md = ""
    md_path = rdir / "report.md"
    if md_path.exists():
        try:
            report_md = md_path.read_text(encoding="utf-8")
        except Exception:
            report_md = ""
    # sources embedded in report.md — extract [S#] lines if present
    sources: list[dict[str, Any]] = []
    # also try to read structured sources if stats.csv sidecar not available; report.md lines
    # For now return raw md + parsed stats + map refs
    map_png = rdir / "map.png"
    zonal_csvs = sorted(rdir.glob("zonal_*.csv"))
    files = []
    for p in sorted(rdir.glob("*")):
        if p.is_file():
            files.append({"path": str(p.relative_to(rdir)), "full": str(p), "size": p.stat().st_size})

    # worst date / trend
    trend: dict[str, Any] | None = None
    if stats:
        # find mean key
        mean_key = next((k for k in stats[0].keys() if k.startswith("mean_")), None)
        if mean_key:
            vals = [r.get(mean_key) for r in stats if isinstance(r.get(mean_key), (int, float))]
            if vals:
                worst = min(stats, key=lambda r: r.get(mean_key) if isinstance(r.get(mean_key), (int, float)) else 9e9)
                trend = {
                    "first": stats[0].get(mean_key),
                    "last": stats[-1].get(mean_key),
                    "worst_date": worst.get("date"),
                    "worst_mean": worst.get(mean_key),
                    "worst_label": worst.get("stress_label"),
                    "count": len(stats),
                }

    return {
        "farm_id": farm_id,
        "dir": str(rdir),
        "report_md": report_md,
        "stats": stats,
        "map_png": str(map_png) if map_png.exists() else None,
        "zonal_csvs": [str(p) for p in zonal_csvs],
        "files": files,
        "trend": trend,
        "sources": sources,
    }


@router.post("/{farm_id}/report")
async def create_farm_report(farm_id: str, body: FarmReportRequest) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    # validate farm exists loosely
    _, features = _find_farms_geojson()
    if not any(str((f.get("properties") or {}).get("farm_id")) == farm_id for f in features):
        # allow creation even if not in registry? Return 404 to be explicit
        raise GeoFrontError(code="farm_not_found", message=f"Farm not found: {farm_id}", status_code=404)

    farms_path = body.farms_path
    if not farms_path:
        # reuse discovered source
        src, _ = _find_farms_geojson()
        farms_path = str(src) if src else "farms.geojson"
    raster_glob = body.raster_glob or "rasters/*.tif"
    indices = body.indices or ["NDVI"]

    service = get_agent_service()
    if not service.is_initialized:
        raise GeoFrontError(code="agent_not_ready", message="Agent not initialized", status_code=409)

    import time

    from geoagent.registry import RunContext

    def _run() -> dict[str, Any]:
        registry = service.registry
        tool_def = registry.get("geo_farm_report")
        if tool_def is None:
            raise RuntimeError("geo_farm_report tool not registered")
        ctx = RunContext(
            store=service.store,
            workspace_dir=service._settings.workspace,
            sandbox_roots=service._settings.resolve_sandbox_roots(),
            settings=service._settings,
            max_tool_calls=500,
            deadline=time.monotonic() + tool_def.timeout_s,
        )
        args: dict[str, Any] = {
            "farm_id": farm_id,
            "farms_path": farms_path,
            "raster_glob": raster_glob,
            "indices": indices,
        }
        if body.raster_paths:
            args["raster_paths"] = body.raster_paths
        if body.out_dir:
            args["out_dir"] = body.out_dir
        result = registry.call("geo_farm_report", args, ctx)
        return result.model_dump(mode="json")

    mgr = get_job_manager()
    record = await mgr.submit("farm_report", _run)
    return {"job_id": record.id, "status": record.status}


@router.get("/{farm_id}/recommend")
async def get_recommendation(
    farm_id: str,
    topic: str = Query(default="irrigation", pattern="^(irrigation|fertilization|spraying)$"),
    report_dir: str | None = Query(default=None),
) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    service = get_agent_service()
    if not service.is_initialized:
        raise GeoFrontError(code="agent_not_ready", message="Agent not initialized", status_code=409)

    # resolve report_dir if not given
    if not report_dir:
        slug = farm_id.replace("/", "_")
        for p in _report_dirs():
            if p.name == slug:
                report_dir = str(p)
                break

    import time

    from geoagent.registry import RunContext

    registry = service.registry
    tool_def = registry.get("geo_recommend")
    if tool_def is None:
        raise GeoFrontError(code="tool_not_found", message="geo_recommend not available", status_code=404)

    ctx = RunContext(
        store=service.store,
        workspace_dir=service._settings.workspace,
        sandbox_roots=service._settings.resolve_sandbox_roots(),
        settings=service._settings,
        max_tool_calls=50,
        deadline=time.monotonic() + tool_def.timeout_s,
    )
    args: dict[str, Any] = {"topic": topic, "farm_id": farm_id}
    if report_dir:
        args["report_dir"] = report_dir
    result = registry.call("geo_recommend", args, ctx)
    return result.model_dump(mode="json")
