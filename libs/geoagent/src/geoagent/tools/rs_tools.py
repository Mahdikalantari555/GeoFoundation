"""Remote-sensing tools: METRIC ETa pipeline wrapper for Landsat scenes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from geoagent.registry import (
    ArtifactRef,
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)

_OUTPUT_PRODUCTS = [
    "ET_daily",
    "ETrF",
    "LE",
    "H",
    "Rn",
    "G",
    "dT",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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

        landsat_dir = Path(args["landsat_dir"])
        output_dir = Path(args["output_dir"])

        if not landsat_dir.exists():
            return ToolResult(
                status="failed",
                error=f"landsat_dir does not exist: {landsat_dir}",
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        config = args.get("config") or {}
        pipeline = METRICPipeline(config=config)

        try:
            pipeline.run(
                landsat_dir=str(landsat_dir),
                meteo_data={},
                output_dir=str(output_dir),
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(status="failed", error=f"pipeline failed: {exc}")

        artifacts: list[ArtifactRef] = []
        for name in _OUTPUT_PRODUCTS:
            matches = list(output_dir.glob(f"*{name}*.tif"))
            if matches:
                p = matches[0]
                artifacts.append(ArtifactRef(path=str(p), sha256=_sha256(p)))

        return ToolResult(
            status="ok",
            value={
                "artifacts_count": len(artifacts),
                "output_dir": str(output_dir),
                "products_found": [a.path for a in artifacts],
            },
            artifacts=artifacts,
        )
