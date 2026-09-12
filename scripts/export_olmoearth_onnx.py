#!/usr/bin/env python3
"""Export OLMoEarth Nano v1.2 PyTorch checkpoint to ONNX format.

Usage:
    python scripts/export_olmoearth_onnx.py \\
        --input /path/to/weights.pth \\
        --output /path/to/onnx_dir

Requirements (optional): ``torch``, ``onnx``. If either is absent the script
exits with code 1 and a clear message so consumers (CI, human) can skip the
spike without treating it as a library failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export OLMoEarth Nano v1.2 to ONNX")
    parser.add_argument("--input", required=True, help="Path to weights.pth")
    parser.add_argument("--output", required=True, help="Output directory for .onnx + config")
    args = parser.parse_args()

    weights_path = Path(args.input)
    output_dir = Path(args.output)

    # ── Dependency check ────────────────────────────────────────────────────
    try:
        import torch  # noqa: F401
    except ImportError as exc:  # pragma: no cover - missing optional dep
        print(f"torch unavailable — cannot run export: {exc}")
        return 1

    try:
        import onnx  # noqa: F401
    except ImportError as exc:  # pragma: no cover - missing optional dep
        print(f"onnx unavailable — cannot run export: {exc}")
        return 1

    # ── Input validation ────────────────────────────────────────────────────
    if not weights_path.is_file():
        print(f"weights file not found: {weights_path}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load model via olmoearth_pretrain (same path used by OlmoEarthVisionEmbedder) ──
    try:
        from olmoearth_pretrain.config import Config  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - spike-only
        print(f"olmoearth_pretrain not available — cannot load model: {exc}")
        return 1

    config_path = weights_path.parent / "config.json"
    if not config_path.is_file():
        print(f"config.json not found at {config_path}; skipping export")
        return 1

    with config_path.open() as f:
        config_dict = json.load(f)

    enc = config_dict.get("model", {}).get("encoder_config", {})
    if isinstance(enc, dict) and "use_linear_patch_embed" not in enc:
        config_dict["model"]["encoder_config"]["use_linear_patch_embed"] = False

    try:
        model_config = Config.from_dict(config_dict["model"])
        model = model_config.build()
        state_dict = torch.load(str(weights_path), map_location="cpu")
        model.load_state_dict(state_dict)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to load model from {weights_path}: {exc}")
        return 1

    model.eval()

    # ── Export to ONNX ──────────────────────────────────────────────────────
    dummy_input = torch.zeros(1, 128, 128, 1, 12)
    onnx_path = output_dir / "model.onnx"
    try:
        torch.onnx.export(
            model.encoder,
            dummy_input,
            str(onnx_path),
            opset_version=17,
            input_names=["input"],
            output_names=["embedding"],
            dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ONNX export failed: {exc}")
        return 1

    # ── Write manifest ──────────────────────────────────────────────────────
    manifest = {
        "model": "olmoearth-nano-v1.2",
        "format": "onnx",
        "opset_version": 17,
        "input_shape": [1, 128, 128, 1, 12],
        "output_dim": 128,
        "source_weights": str(weights_path),
        "exported_at": Path(__file__).resolve().stem,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"Exported ONNX model to {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
