"""Remote-sensing tools: METRIC ETa pipeline wrapper for Landsat scenes."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, cast

from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

_OUTPUT_PATTERNS = {
    "ET_daily": ("*ETaDaily*.tif", "*ET_daily*.tif"),
    "ETrF": ("*ETrF*.tif",),
    "LE": ("*LE*.tif",),
    "H": ("*H*.tif",),
    "Rn": ("*Rn*.tif",),
    "G": ("*G*.tif",),
    "dT": ("*dT*.tif",),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve(ctx: RunContext, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else ctx.workspace_dir / path


def _finite_values(value: Any) -> list[float]:
    """Return finite numeric values from a scalar or array-like result."""
    if hasattr(value, "values"):
        value = value.values
    try:
        import numpy as np

        values = np.asarray(value, dtype=float)
        return [float(item) for item in values[np.isfinite(values)].tolist()]
    except (ImportError, TypeError, ValueError, OverflowError):
        return []


def _summary(results: Any) -> dict[str, float | str | None]:
    """Build the compact ET statistics returned by the tool."""
    result_map = results if isinstance(results, dict) else {}
    et_daily = _finite_values(result_map.get("ET_daily"))
    etrf = _finite_values(result_map.get("ETrF"))

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    def std(values: list[float], average: float | None) -> float | None:
        if not values or average is None:
            return None
        variance = sum((value - average) ** 2 for value in values) / len(values)
        return math.sqrt(variance)

    et_daily_mean = mean(et_daily)
    return {
        "ET_daily_mean": et_daily_mean,
        "ET_daily_std": std(et_daily, et_daily_mean),
        "ETrF_mean": mean(etrf),
    }


def _quality(pipeline: Any) -> str:
    """Return the pipeline's scalar scene-quality label."""
    getter = getattr(pipeline, "get_scene_quality", None)
    if getter is None:
        return "UNKNOWN"
    try:
        quality = getter()
    except Exception:  # noqa: BLE001
        return "UNKNOWN"
    if isinstance(quality, dict):
        quality = quality.get("quality", "UNKNOWN")
    return str(quality) if quality is not None else "UNKNOWN"


def _artifacts(output_dir: Path) -> list[ArtifactRef]:
    """Collect one artifact for each requested METRIC output product."""
    artifacts: list[ArtifactRef] = []
    seen: set[Path] = set()
    for product, patterns in _OUTPUT_PATTERNS.items():
        for pattern in patterns:
            matches = sorted(
                path
                for path in output_dir.glob(pattern)
                if path.is_file() and (
                    product == "ET_daily"
                    or path.name.startswith(product)
                )
            )
            if not matches:
                continue
            path = matches[0]
            if path not in seen:
                artifacts.append(ArtifactRef(path=str(path), sha256=_sha256(path)))
                seen.add(path)
            break
    return artifacts


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="rs_compute_et",
            description=(
                "Run the full METRIC ETa pipeline on a Landsat Collection 2 "
                "Level-2 scene directory. Writes ET_daily.tif, ETrF.tif, LE.tif, "
                "H.tif, Rn.tif, G.tif, dT.tif to output_dir."
            ),
            params={
                "type": "object",
                "properties": {
                    "landsat_dir": {
                        "type": "string",
                        "description": "Path to a Landsat L2 scene directory containing MTL.json.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where ET products will be written.",
                    },
                    "config": {
                        "type": "object",
                        "description": "Optional METRIC config dict (band_mapping, calibration, etc.).",
                    },
                },
                "required": ["landsat_dir", "output_dir"],
                "additionalProperties": False,
            },
            timeout_s=600.0,
            cacheable=False,
        )
    )
    def rs_compute_et(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        # Lazy import — structured error when [rs] extra is missing.
        try:
            from data_engine.landsat import METRICPipeline
        except ImportError:
            return ToolResult(
                status="validation_error",
                error="data-engine [rs] extra not installed; run: pip install geoagent[rs]",
            )

        landsat_dir = _resolve(ctx, args["landsat_dir"])
        output_dir = _resolve(ctx, args["output_dir"])

        if not landsat_dir.exists():
            return ToolResult(
                status="failed",
                error=f"landsat_dir does not exist: {landsat_dir}",
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        config = args.get("config") or {}
        pipeline = METRICPipeline(config=config)

        try:
            results = pipeline.run(
                landsat_dir=str(landsat_dir),
                meteo_data=cast(dict[Any, Any], []),
                output_dir=str(output_dir),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="failed", error=f"pipeline failed: {exc}")

        value = _summary(results)
        value["quality"] = _quality(pipeline)
        artifacts = _artifacts(output_dir)
        return ToolResult(status="ok", value=value, artifacts=artifacts)
