"""GIS tools: spectral indices, reclassify, polygonize, symbology, zonal stats.

All rasterio/geopandas/shapely/matplotlib imports are lazy (inside functions)
so the base install works without the ``rs`` extras. All tools are
deterministic and cacheable; file outputs are artifact-hashed by the registry.
"""

from __future__ import annotations

import csv
import json
import os

# Headless-safe rendering: must precede any matplotlib import. Tools execute
# in registry worker threads; a GUI backend (Tk) would abort at teardown.
os.environ.setdefault("MPLBACKEND", "Agg")

from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np

from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

DEFAULT_BAND_MAP = {"blue": 2, "green": 3, "red": 4, "nir": 8}
NODATA_FLOAT = -9999.0
NODATA_INT = -9999


def _require(module: str, extra: str = "geoagent[rs]") -> Any:
    try:
        return __import__(module)
    except ImportError as exc:
        raise RuntimeError(f"'{module}' is required for this tool — install {extra}") from exc


def _ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    denom = nir + red
    out = np.full_like(denom, np.nan, dtype=np.float64)
    np.divide(nir - red, denom, out=out, where=denom != 0)
    return out


def _evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    denom = nir + 6.0 * red - 7.5 * blue + 1.0
    out = np.full_like(denom, np.nan, dtype=np.float64)
    np.divide(2.5 * (nir - red), denom, out=out, where=denom != 0)
    return out


def _ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    denom = green + nir
    out = np.full_like(denom, np.nan, dtype=np.float64)
    np.divide(green - nir, denom, out=out, where=denom != 0)
    return out


def _savi(red: np.ndarray, nir: np.ndarray, l: float = 0.5) -> np.ndarray:
    denom = nir + red + l
    out = np.full_like(denom, np.nan, dtype=np.float64)
    np.divide(1.5 * (nir - red), denom, out=out, where=denom != 0)
    return out


def _compute_index(name: str, bands: dict[str, np.ndarray]) -> np.ndarray:
    upper = name.upper()
    if upper == "NDVI":
        return _ndvi(bands["nir"], bands["red"])
    if upper == "EVI":
        return _evi(bands["nir"], bands["red"], bands["blue"])
    if upper == "NDWI":
        return _ndwi(bands["green"], bands["nir"])
    if upper == "SAVI":
        return _savi(bands["red"], bands["nir"])
    raise ValueError(f"unsupported index '{name}' (supported: NDVI, EVI, NDWI, SAVI)")


def _stats(arr: np.ndarray) -> dict[str, float]:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return {"count": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "p05": 0.0, "p95": 0.0}
    return {
        "count": float(finite.size),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "p05": float(np.percentile(finite, 5)),
        "p95": float(np.percentile(finite, 5 + 90)),
    }


def _resolve(ctx: RunContext, raw: str) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else ctx.workspace_dir / p


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="geo_compute_indices",
            description=(
                "Compute spectral indices (NDVI, EVI, NDWI, SAVI) from a multiband "
                "GeoTIFF; writes one float32 GeoTIFF per index plus summary stats. "
                "Default Sentinel-2 band map: blue=2 green=3 red=4 nir=8 (1-based)."
            ),
            params={
                "type": "object",
                "properties": {
                    "input_tif": {"type": "string"},
                    "indices": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["NDVI", "EVI", "NDWI", "SAVI"]},
                        "minItems": 1,
                    },
                    "band_map": {
                        "type": "object",
                        "properties": {
                            name: {"type": "integer"} for name in ("blue", "green", "red", "nir")
                        },
                        "description": "1-based band indices per name",
                    },
                    "output_dir": {"type": "string"},
                },
                "required": ["input_tif", "indices"],
                "additionalProperties": False,
            },
            returns="per-index stats + output tif paths",
            timeout_s=300.0,
            cacheable=True,
        )
    )
    def geo_compute_indices(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        rasterio = _require("rasterio")
        src_path = _resolve(ctx, args["input_tif"])
        band_map = {**DEFAULT_BAND_MAP, **(args.get("band_map") or {})}
        out_dir = _resolve(ctx, args.get("output_dir") or f"runs/indices/{src_path.stem}")
        out_dir.mkdir(parents=True, exist_ok=True)

        with rasterio.open(src_path) as src:
            profile = src.profile.copy()
            arrs: dict[str, np.ndarray] = {}
            for idx_name in args["indices"]:
                for b in _NEEDS[idx_name.upper()]:
                    if b not in arrs:
                        arrs[b] = src.read(band_map[b]).astype(np.float64)

        profile.update(count=1, dtype="float32", nodata=NODATA_FLOAT)
        artifacts: list[ArtifactRef] = []
        summary: dict[str, Any] = {}
        for idx_name in args["indices"]:
            upper = idx_name.upper()
            missing = [b for b in _NEEDS[upper] if b not in arrs]
            if missing:
                return ToolResult(status="validation_error", error=f"{upper} needs bands {missing}")
            result_arr = _compute_index(upper, arrs)
            result_arr = np.nan_to_num(result_arr, nan=NODATA_FLOAT)
            out_path = out_dir / f"{src_path.stem}_{upper.lower()}.tif"
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(result_arr.astype("float32"), 1)
            clean = result_arr[result_arr != NODATA_FLOAT]
            summary[upper] = {"stats": _stats(clean), "tif": str(out_path)}
            artifacts.append(ArtifactRef(path=str(out_path)))
        return ToolResult(status="ok", value={"indices": summary}, artifacts=artifacts)

    @registry.register(
        ToolDefinition(
            name="geo_reclassify",
            description=(
                "Reclassify raster values into classes via rules [{min,max,out}] "
                "(min inclusive, max exclusive). Pixels outside all rules become nodata."
            ),
            params={
                "type": "object",
                "properties": {
                    "input_tif": {"type": "string"},
                    "rules": {
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
                        "minItems": 1,
                    },
                    "output_tif": {"type": "string"},
                },
                "required": ["input_tif", "rules", "output_tif"],
                "additionalProperties": False,
            },
            returns="class histogram + output path",
            timeout_s=300.0,
            cacheable=True,
        )
    )
    def geo_reclassify(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        rasterio = _require("rasterio")
        rules = sorted(args["rules"], key=lambda r: r["min"])
        for a, b in pairwise(rules):
            if a["max"] > b["min"]:
                return ToolResult(
                    status="validation_error",
                    error=f"overlapping rules: [{a['min']},{a['max']}) vs [{b['min']},{b['max']})",
                )

        src_path = _resolve(ctx, args["input_tif"])
        out_path = _resolve(ctx, args["output_tif"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(src_path) as src:
            data = src.read(1).astype(np.float64)
            nodata = src.nodata
            valid = np.isfinite(data) if nodata is None else np.isfinite(data) & (data != nodata)
            out = np.full(data.shape, NODATA_INT, dtype=np.int32)
            for rule in rules:
                mask = valid & (data >= rule["min"]) & (data < rule["max"])
                out[mask] = int(rule["out"])
            profile = src.profile.copy()
            profile.update(count=1, dtype="int32", nodata=NODATA_INT)
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(out, 1)
        vals, counts = np.unique(out[out != NODATA_INT], return_counts=True)
        histogram = {str(int(v)): int(c) for v, c in zip(vals, counts)}
        return ToolResult(
            status="ok",
            value={"histogram": histogram, "nodata_pixels": int((out == NODATA_INT).sum())},
            artifacts=[ArtifactRef(path=str(out_path))],
        )

    @registry.register(
        ToolDefinition(
            name="geo_polygonize",
            description=(
                "Convert a classified raster to polygons (GeoJSON FeatureCollection). "
                "Optional simplify_tolerance in CRS units (requires shapely)."
            ),
            params={
                "type": "object",
                "properties": {
                    "input_tif": {"type": "string"},
                    "output_geojson": {"type": "string"},
                    "value_field": {"type": "string"},
                    "simplify_tolerance": {"type": "number"},
                },
                "required": ["input_tif", "output_geojson"],
                "additionalProperties": False,
            },
            returns="feature count + class areas summary",
            timeout_s=300.0,
            cacheable=True,
        )
    )
    def geo_polygonize(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        rasterio = _require("rasterio")
        from rasterio.features import shapes

        src_path = _resolve(ctx, args["input_tif"])
        out_path = _resolve(ctx, args["output_geojson"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        value_field = args.get("value_field") or "class"
        tolerance = args.get("simplify_tolerance")

        with rasterio.open(src_path) as src:
            data = src.read(1)
            mask = data != (src.nodata if src.nodata is not None else NODATA_INT)
            geoms = shapes(data, mask=mask, transform=src.transform)
            features = []
            class_area: dict[str, float] = {}
            epsg = src.crs.to_epsg() if src.crs else None
            for geom, value in geoms:
                if tolerance is not None:
                    shapely = _require("shapely")
                    shape_obj = shapely.geometry.shape(geom).simplify(tolerance)
                    geom = shapely.geometry.mapping(shape_obj)
                area = _polygon_area_deg2(geom)
                features.append(
                    {
                        "type": "Feature",
                        "properties": {value_field: int(value), "area_deg2": round(area, 6)},
                        "geometry": geom,
                    }
                )
                key = str(int(value))
                class_area[key] = class_area.get(key, 0.0) + area

        fc = {
            "type": "FeatureCollection",
            "features": features,
            **({"crs": {"type": "name", "properties": {"name": f"EPSG:{epsg}"}}} if epsg else {}),
        }
        out_path.write_text(json.dumps(fc), encoding="utf-8")
        total = sum(class_area.values()) or 1.0
        share = {k: round(100.0 * v / total, 2) for k, v in class_area.items()}
        return ToolResult(
            status="ok",
            value={"feature_count": len(features), "area_share_pct_by_class": share},
            artifacts=[ArtifactRef(path=str(out_path))],
        )

    @registry.register(
        ToolDefinition(
            name="geo_zonal_stats",
            description=(
                "Per-polygon statistics of a raster: mean/min/max/std/count/nodata_share. "
                "Writes CSV; id_field names the polygon property used as row key."
            ),
            params={
                "type": "object",
                "properties": {
                    "raster_tif": {"type": "string"},
                    "polygons_geojson": {"type": "string"},
                    "id_field": {"type": "string"},
                    "out_csv": {"type": "string"},
                },
                "required": ["raster_tif", "polygons_geojson", "out_csv"],
                "additionalProperties": False,
            },
            returns="rows summary + worst-mean ids first",
            timeout_s=300.0,
            cacheable=True,
        )
    )
    def geo_zonal_stats(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        rasterio = _require("rasterio")
        from rasterio.mask import mask as rio_mask

        raster_path = _resolve(ctx, args["raster_tif"])
        poly_path = _resolve(ctx, args["polygons_geojson"])
        out_path = _resolve(ctx, args["out_csv"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        id_field = args.get("id_field") or "farm_id"

        fc = json.loads(poly_path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]] = []
        with rasterio.open(raster_path) as src:
            nodata = src.nodata
            for feature in fc.get("features", []):
                props = feature.get("properties", {})
                row_id = props.get(id_field, f"poly_{len(rows)}")
                try:
                    clipped, _ = rio_mask(src, [feature["geometry"]], crop=True, filled=False)
                except ValueError as exc:
                    rows.append({id_field: row_id, "error": str(exc)[:120]})
                    continue
                band = clipped[0].astype(np.float64)
                if nodata is not None:
                    band = np.where(band == nodata, np.nan, band)
                st = _stats(band)
                total_px = band.size
                st["nodata_share"] = (
                    round(float((~np.isfinite(band)).sum()) / total_px, 4) if total_px else 1.0
                )
                rows.append({id_field: row_id, **{k: round(v, 4) for k, v in st.items()}})

        fieldnames = sorted({k for r in rows for k in r})
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        numeric = [
            r for r in rows if isinstance(r.get(id_field), (str, int)) and "mean" in r
        ]
        worst = sorted(numeric, key=lambda r: r["mean"])[:5]
        return ToolResult(
            status="ok",
            value={
                "row_count": len(rows),
                "csv": str(out_path),
                "lowest_mean_first": [
                    {id_field: r[id_field], "mean": r["mean"]} for r in worst
                ],
            },
            artifacts=[ArtifactRef(path=str(out_path))],
        )

    @registry.register(
        ToolDefinition(
            name="geo_symbology",
            description=(
                "Render a classified choropleth PNG from GeoJSON. classification: "
                "{scheme: quantiles|equal_interval|manual, n_classes, breaks} over "
                "numeric `field`. Returns class-break table + feature counts."
            ),
            params={
                "type": "object",
                "properties": {
                    "input_geojson": {"type": "string"},
                    "field": {"type": "string"},
                    "classification": {
                        "type": "object",
                        "properties": {
                            "scheme": {
                                "type": "string",
                                "enum": ["quantiles", "equal_interval", "manual"],
                            },
                            "n_classes": {"type": "integer", "minimum": 2},
                            "breaks": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["scheme"],
                    },
                    "palette": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "hex colors; default RdYlGn_r",
                    },
                    "out_png": {"type": "string"},
                },
                "required": ["input_geojson", "field", "classification", "out_png"],
                "additionalProperties": False,
            },
            returns="break table, count per class, png path",
            timeout_s=180.0,
            cacheable=True,
        )
    )
    def geo_symbology(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        _require("matplotlib")
        os.environ.setdefault("MPLBACKEND", "Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgba
        from matplotlib.patches import Patch

        fc = json.loads(_resolve(ctx, args["input_geojson"]).read_text(encoding="utf-8"))
        features = fc.get("features", [])
        field = args["field"]
        values = [f["properties"].get(field) for f in features]
        numeric = [float(v) for v in values if isinstance(v, (int, float))]
        if not numeric:
            return ToolResult(status="validation_error", error=f"no numeric values for field '{field}'")

        cls = args["classification"]
        scheme = cls["scheme"]
        if scheme == "manual":
            breaks = sorted(float(b) for b in cls.get("breaks") or [])
            if len(breaks) < 2:
                return ToolResult(status="validation_error", error="manual scheme needs >= 2 breaks")
        elif scheme == "quantiles":
            n = int(cls.get("n_classes") or 4)
            qs = np.quantile(numeric, [i / n for i in range(1, n)])
            breaks = [min(numeric)] + [float(q) for q in qs] + [max(numeric)]
        else:
            n = int(cls.get("n_classes") or 4)
            lo, hi = min(numeric), max(numeric)
            breaks = list(np.linspace(lo, hi, n + 1))

        palette = args.get("palette") or ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]
        colors = [palette[i % len(palette)] for i in range(len(breaks) - 1)]

        def class_index_for(v: Any) -> int | None:
            if not isinstance(v, (int, float)):
                return None
            for i in range(len(breaks) - 1):
                lo_i, hi_i = breaks[i], breaks[i + 1]
                if (lo_i <= v < hi_i) or (i == len(breaks) - 2 and v <= hi_i):
                    return i
            return None

        out_png = _resolve(ctx, args["out_png"])
        out_png.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(8, 8))
        counts: dict[int, int] = {}
        for feature in features:
            idx = class_index_for(feature["properties"].get(field))
            if idx is None:
                continue
            geom = feature["geometry"]
            if geom["type"] == "Polygon":
                polygon_parts = [geom["coordinates"]]
            else:
                polygon_parts = geom["coordinates"]
            for rings in polygon_parts:
                exterior = rings[0]
                xs = [pt[0] for pt in exterior]
                ys = [pt[1] for pt in exterior]
                ax.fill(xs, ys, facecolor=to_rgba(colors[idx], 0.75), edgecolor="#333333", linewidth=0.4)
            counts[idx] = counts.get(idx, 0) + 1

        handles = [
            Patch(facecolor=colors[i], edgecolor="#333333",
                  label=f"[{breaks[i]:.3g}, {breaks[i+1]:.3g})" + ("]" if i == len(colors) - 1 else ")"))
            for i in range(len(colors))
        ]
        ax.legend(handles=handles, title=field, loc="lower left", fontsize=8)
        ax.set_aspect("equal")
        ax.set_title(field)
        fig.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.close(fig)

        break_table = [
            {"class": i, "range": [breaks[i], breaks[i + 1]], "color": colors[i],
             "features": counts.get(i, 0)}
            for i in range(len(colors))
        ]
        return ToolResult(
            status="ok",
            value={"png": str(out_png), "classes": break_table},
            artifacts=[ArtifactRef(path=str(out_png))],
        )


_NEEDS: dict[str, tuple[str, ...]] = {
    "NDVI": ("nir", "red"),
    "EVI": ("nir", "red", "blue"),
    "NDWI": ("green", "nir"),
    "SAVI": ("red", "nir"),
}


def _polygon_area_deg2(geom: dict[str, Any]) -> float:
    rings = []
    if geom["type"] == "Polygon":
        rings = [geom["coordinates"][0]]
    elif geom["type"] == "MultiPolygon":
        rings = [poly[0] for poly in geom["coordinates"]]
    total = 0.0
    for ring in rings:
        pts = list(ring)
        s = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            s += x1 * y2 - x2 * y1
        total += abs(s) / 2.0
    return total
