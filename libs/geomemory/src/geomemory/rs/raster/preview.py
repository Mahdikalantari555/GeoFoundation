"""Preview generation for raster scenes and tiles."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def compute_preview_array(
    arr: np.ndarray,
    *,
    max_side: int = 512,
    rgb_bands: tuple[int, int, int] = (3, 2, 1),
) -> np.ndarray:
    """Normalize a (bands, height, width) or (height, width) array to uint8 RGB.

    The output is an (H, W, 3) uint8 array suitable for PNG encoding. Pure
    numpy so it is fully testable without Pillow or rasterio.
    """
    array = np.asarray(arr, dtype=np.float32)
    if array.ndim == 3:
        composed = _compose_rgb(array, rgb_bands)
    elif array.ndim == 2:
        gray = array[np.newaxis, :, :]
        composed = np.repeat(gray, 3, axis=0)
    else:
        raise ValueError(f"preview input must be 2D or 3D, got {array.ndim}D")
    resized = _downsample_mean(composed, max_side=max_side)
    return _normalize_uint8(resized).transpose(1, 2, 0)


def write_png(array: np.ndarray, path: str | Path) -> bool:
    """Write an array to a PNG file. Returns False when Pillow is unavailable."""
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - optional dependency
        return False
    arr = np.asarray(array)
    if arr.ndim == 3 and arr.shape[-1] == 3:
        image = Image.fromarray(arr, mode="RGB")
    else:
        image = Image.fromarray(arr, mode="L")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(target), format="PNG")
    return True


def _compose_rgb(arr: np.ndarray, rgb_bands: tuple[int, int, int]) -> np.ndarray:
    """Pick 1-based bands for (R, G, B), falling back to available channels."""
    out = np.zeros((3, arr.shape[1], arr.shape[2]), dtype=np.float32)
    assigned = [False, False, False]
    for out_idx, band in enumerate(rgb_bands):
        if 1 <= band <= arr.shape[0]:
            out[out_idx] = arr[band - 1]
            assigned[out_idx] = True
    fallback = list(range(arr.shape[0]))
    for i in range(3):
        if not assigned[i]:
            source = arr[fallback[i % len(fallback)]] if fallback else np.zeros_like(arr[0])
            out[i] = source
    return out


def _downsample_mean(arr: np.ndarray, *, max_side: int) -> np.ndarray:
    """Average-pool a (C, H, W) array so its longest side is <= max_side."""
    height, width = arr.shape[-2:]
    scale = min(1.0, max_side / max(height, width))
    if scale >= 1.0:
        return arr
    new_h = max(1, round(height * scale))
    new_w = max(1, round(width * scale))
    rows = np.linspace(0, height, new_h + 1, dtype=int)
    cols = np.linspace(0, width, new_w + 1, dtype=int)
    out = np.empty((arr.shape[0], new_h, new_w), dtype=np.float32)
    for i in range(new_h):
        y0 = rows[i]
        y1 = max(y0 + 1, rows[i + 1])
        for j in range(new_w):
            x0 = cols[j]
            x1 = max(x0 + 1, cols[j + 1])
            out[:, i, j] = arr[:, y0:y1, x0:x1].mean(axis=(1, 2))
    return out


def _normalize_uint8(arr: np.ndarray) -> np.ndarray:
    """Percentile-clip and scale an array to uint8 (0-255)."""
    low, high = np.percentile(arr, [2, 98])
    if high <= low:
        high = low + 1e-6
    scaled = np.clip((arr - low) / (high - low), 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)
