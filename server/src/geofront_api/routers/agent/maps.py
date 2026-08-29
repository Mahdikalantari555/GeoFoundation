"""Maps artifact viewer endpoints (M6 Geo)."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from ...errors import GeoFrontError
from ...services.agent import get_agent_service
from ...state import get_state

router = APIRouter(prefix="/agent/maps", tags=["agent"])
log = logging.getLogger("geofront.agent.maps")

KIND_BY_EXT = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "raster",
    ".tiff": "raster",
    ".geojson": "vector",
    ".json": "vector",
    ".csv": "table",
    ".md": "document",
}


def _roots() -> list[Path]:
    roots: list[Path] = []
    state = get_state()
    if state.workspace_path is not None:
        roots.append(Path(state.workspace_path))
    try:
        svc = get_agent_service()
        if svc.is_initialized:
            roots.append(Path(svc._settings.workspace))
            roots.append(Path(svc._settings.workspace).parent)
    except Exception as exc:  # noqa: BLE001
        log.debug("maps roots lookup failed: %s", exc)
    seen: set[str] = set()
    uniq: list[Path] = []
    for r in roots:
        k = str(r.resolve()) if r.exists() else str(r)
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def _collect_artifacts(pattern: str = "runs/**/*") -> list[dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for root in _roots():
        if not root.exists():
            continue
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            # only interesting artifacts
            if p.suffix.lower() not in (".png", ".geojson", ".json", ".csv", ".tif", ".tiff", ".md"):
                continue
            key = str(p.resolve())
            if key in files:
                continue
            rel: str
            try:
                rel = str(p.relative_to(root))
            except ValueError:
                rel = str(p)
            # prefer relative to workspace
            # try to make relative to main workspace for UI download path
            dl_path = rel
            # if root is agent workspace, make relative to its parent as well for display
            ext = p.suffix.lower()
            files[key] = {
                "path": dl_path,
                "full_path": str(p),
                "name": p.name,
                "kind": KIND_BY_EXT.get(ext, "other"),
                "ext": ext,
                "size": p.stat().st_size,
                "modified": p.stat().st_mtime,
                "dir": str(p.parent.relative_to(root)) if p.parent != root else "",
            }
    return sorted(files.values(), key=lambda x: x["modified"], reverse=True)


@router.get("")
async def list_maps(pattern: str = Query(default="runs/**/*")) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    artifacts = _collect_artifacts(pattern)
    # layer summary for UI: group by kind
    layers = []
    for a in artifacts:
        label = a["name"]
        if a["kind"] == "image" and a["name"] == "map.png":
            label = f"{a['dir']}/map.png" if a["dir"] else "map.png"
        layers.append(
            {
                "id": a["path"],
                "path": a["path"],
                "full_path": a["full_path"],
                "name": a["name"],
                "kind": a["kind"],
                "label": label,
                "size": a["size"],
                "dir": a["dir"],
                "ext": a["ext"],
            }
        )

    # try to extract symbology legend from latest GeoJSON if present
    legend: list[dict[str, Any]] | None = None
    for a in artifacts:
        if a["kind"] == "vector" and a["ext"] == ".geojson":
            try:
                fc = json.loads(Path(a["full_path"]).read_text(encoding="utf-8"))
                feats = fc.get("features", [])
                # count by class if present
                counts: dict[str, int] = {}
                for feat in feats[:500]:
                    props = feat.get("properties") or {}
                    for k in ("class", "Class", "stress_class"):
                        if k in props:
                            counts[str(props[k])] = counts.get(str(props[k]), 0) + 1
                            break
                if counts:
                    legend = [{"class": k, "count": v} for k, v in sorted(counts.items())]
                    break
            except Exception as exc:  # noqa: BLE001
                log.debug("legend parse failed for %s: %s", a["full_path"], exc)
                continue

    return {
        "artifacts": artifacts,
        "layers": layers,
        "count": len(artifacts),
        "pattern": pattern,
        "legend": legend,
    }


@router.get("/geojson")
async def get_geojson(path: str = Query(description="relative artifact path")) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    # resolve sandboxed
    target: Path | None = None
    for root in _roots():
        cand = (root / path).resolve()
        # ensure within root
        try:
            cand.relative_to(root.resolve())
        except ValueError:
            continue
        if cand.exists() and cand.is_file():
            target = cand
            break
    if target is None:
        raise GeoFrontError(code="file_not_found", message=f"GeoJSON not found: {path}", status_code=404)

    try:
        fc = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GeoFrontError(code="invalid_geojson", message=str(exc), status_code=422) from exc

    feats = fc.get("features", []) if isinstance(fc, dict) else []
    # summarize
    props_keys: set[str] = set()
    for f in feats[:20]:
        props_keys.update((f.get("properties") or {}).keys())

    return {
        "path": path,
        "feature_count": len(feats),
        "properties": sorted(props_keys),
        "geojson": fc if len(feats) <= 300 else {"type": "FeatureCollection", "features": feats[:300], "_truncated": True},
    }


@router.get("/zonal")
async def get_zonal(path: str = Query(description="CSV path relative to workspace")) -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        raise GeoFrontError(code="workspace_not_open", message="No workspace is open.", status_code=409)

    target: Path | None = None
    for root in _roots():
        cand = (root / path).resolve()
        try:
            cand.relative_to(root.resolve())
        except ValueError:
            continue
        if cand.exists() and cand.is_file():
            target = cand
            break
    if target is None:
        raise GeoFrontError(code="file_not_found", message=f"CSV not found: {path}", status_code=404)

    def _read() -> list[dict[str, Any]]:
        rows_local: list[dict[str, Any]] = []
        with open(target, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for i, r in enumerate(reader):
                if i >= 500:
                    break
                rows_local.append(dict(r))
        return rows_local

    try:
        rows = await run_in_threadpool(_read)
    except Exception as exc:
        raise GeoFrontError(code="invalid_csv", message=str(exc), status_code=422) from exc

    fieldnames = list(rows[0].keys()) if rows else []
    return {"path": path, "rows": rows, "count": len(rows), "fields": fieldnames}
