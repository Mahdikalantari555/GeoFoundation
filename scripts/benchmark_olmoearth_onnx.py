#!/usr/bin/env python3
"""Benchmark OLMoEarth ONNX vs native torch embeddings.

Usage:
    python scripts/benchmark_olmoearth_onnx.py \\
        --torch-model /path/to/model_dir \\
        --onnx-model /path/to/onnx_dir \\
        --images /path/to/tile_dir \\
        --runs 50

Produces a JSON report with per-sample cosine distances and aggregate metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _check_deps() -> bool:
    for name, mod in [("torch", "torch"), ("onnx", "onnx"), ("numpy", "numpy")]:
        try:
            __import__(mod)
        except ImportError as exc:  # pragma: no cover - missing optional dep
            print(f"{name} unavailable — cannot run benchmark: {exc}")
            return False
    return True


def _load_torch_embeddings(model_dir: Path, image_paths: list[Path]) -> list[list[float]]:
    try:
        from olmoearth_pretrain.config import Config  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        print(f"olmoearth_pretrain not available: {exc}")
        return []

    config_path = model_dir / "config.json"
    if not config_path.is_file():
        print(f"config.json missing at {config_path}")
        return []

    import json as _json

    with config_path.open() as f:
        config_dict = _json.load(f)

    enc = config_dict.get("model", {}).get("encoder_config", {})
    if isinstance(enc, dict) and "use_linear_patch_embed" not in enc:
        config_dict["model"]["encoder_config"]["use_linear_patch_embed"] = False

    import torch

    model_config = Config.from_dict(config_dict["model"])
    model = model_config.build()
    weights_path = model_dir / "weights.pth"
    if not weights_path.is_file():
        weights_path = model_dir  # may be a direct .pth path
    state_dict = torch.load(str(weights_path), map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()

    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
    from geomemory.embeddings.normalization import l2_normalize

    embedder = OlmoEarthVisionEmbedder(str(model_dir))
    try:
        return l2_normalize(
            embedder.embed_images([str(p) for p in image_paths])
        ).tolist()
    except Exception as exc:  # noqa: BLE001
        print(f"Torch embedding failed: {exc}")
        return []


def _load_onnx_embeddings(onnx_dir: Path, image_paths: list[Path], runs: int) -> tuple[list[list[float]], float]:
    import numpy as np
    import onnx
    import onnxruntime as ort  # type: ignore[import-not-found]

    sess = ort.InferenceSession(str(onnx_dir / "model.onnx"))
    input_name = sess.get_inputs()[0].name

    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
    from geomemory.embeddings.normalization import l2_normalize

    # Build raw inputs using the same preprocessing as OlmoEarthVisionEmbedder.
    embedder = OlmoEarthVisionEmbedder(str(onnx_dir))  # fake path; only used for preprocessing
    arrays = [embedder._to_modality_tensor(str(p)) for p in image_paths]  # type: ignore[attr-defined]
    if not arrays:
        return [], 0.0

    def _pad(arr: np.ndarray) -> np.ndarray:
        h, w, c = arr.shape
        if c < 12:
            padded = np.zeros((h, w, 12), dtype=np.float32)
            padded[:, :, :c] = arr
        else:
            padded = arr[:, :, :12]
        return np.expand_dims(np.expand_dims(padded, 0), -2)

    batch = np.stack([_pad(a) for a in arrays]).astype(np.float32)
    times: list[float] = []
    embeddings: list[list[float]] = []

    for _ in range(runs):
        t0 = __import__("time").perf_counter()
        out = sess.run(None, {input_name: batch})
        dt = (__import__("time").perf_counter() - t0) * 1000
        times.append(dt)
        vectors = l2_normalize(out[0].astype(np.float32)).tolist()
        if not embeddings:
            embeddings = vectors

    return embeddings, sum(times) / len(times) if times else 0.0


def _cosine_distance(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.asarray(a), np.asarray(b)
    norm_a, norm_b = np.linalg.norm(va), np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - np.dot(va, vb) / (norm_a * norm_b))


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark OLMoEarth ONNX vs torch")
    parser.add_argument("--torch-model", required=True, help="Directory containing config.json + weights.pth")
    parser.add_argument("--onnx-model", required=True, help="Directory containing model.onnx + manifest.json")
    parser.add_argument("--images", required=True, help="Directory of tile PNG/JPG images to embed")
    parser.add_argument("--runs", type=int, default=50, help="Number of timing repetitions")
    parser.add_argument("--output", default=None, help="Write results JSON to this path")
    args = parser.parse_args()

    if not _check_deps():
        return 1

    image_dir = Path(args.images)
    image_paths = sorted(image_dir.rglob("*"))[:20]  # cap at 20 tiles
    if not image_paths:
        print("No images found under --images")
        return 1

    print(f"Embedding {len(image_paths)} tiles ...")
    torch_embs = _load_torch_embeddings(Path(args.torch_model), image_paths)
    if not torch_embs:
        print("Torch embedding failed — cannot compare")
        return 1

    onnx_embs, avg_ms = _load_onnx_embeddings(Path(args.onnx_model), image_paths, args.runs)
    if not onnx_embs:
        print("ONNX embedding failed — cannot compare")
        return 1

    distances = [_cosine_distance(t, o) for t, o in zip(torch_embs, onnx_embs)]
    mean_dist = sum(distances) / len(distances) if distances else float("nan")
    quality_ok = mean_dist <= 0.02

    result = {
        "n_samples": len(image_paths),
        "mean_cosine_distance": round(mean_dist, 6),
        "acceptance_threshold": 0.02,
        "quality_acceptable": quality_ok,
        "onnx_avg_latency_ms": round(avg_ms, 2),
        "torch_embedding_dim": len(torch_embs[0]),
        "per_sample_distances": [round(d, 6) for d in distances],
    }

    print(json.dumps(result, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        print(f"\nResults written to {out_path}")

    return 0 if quality_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
