"""Spectral indices and band statistics (pure numpy)."""

from __future__ import annotations

import numpy as np

from geomemory.core.exceptions import BandMappingError
from geomemory.rs.raster.metadata import RasterSceneData


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index: (NIR - RED) / (NIR + RED)."""
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    _check_shapes(nir, red, "NDVI")
    denominator = nir + red
    out = np.full_like(denominator, np.nan)
    np.divide(nir - red, denominator, out=out, where=denominator != 0)
    return out


def evi(
    nir: np.ndarray,
    red: np.ndarray,
    blue: np.ndarray,
    *,
    g: float = 2.5,
    c1: float = 6.0,
    c2: float = 7.5,
    l: float = 1.0,
) -> np.ndarray:
    """Enhanced Vegetation Index with the standard coefficients."""
    nir = np.asarray(nir, dtype=np.float64)
    red = np.asarray(red, dtype=np.float64)
    blue = np.asarray(blue, dtype=np.float64)
    _check_shapes(nir, red, "EVI")
    _check_shapes(nir, blue, "EVI")
    denominator = nir + c1 * red - c2 * blue + l
    out = np.full_like(denominator, np.nan)
    np.divide(g * (nir - red), denominator, out=out, where=denominator != 0)
    return out


def band_statistics(array: np.ndarray) -> dict[str, float]:
    """Compute descriptive statistics for a single-band array."""
    values = np.asarray(array, dtype=np.float64).ravel()
    if values.size == 0:
        return {"count": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "p05": 0.0, "p95": 0.0}
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"count": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0, "p05": 0.0, "p95": 0.0}
    return {
        "count": float(finite.size),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "p05": float(np.percentile(finite, 5)),
        "p95": float(np.percentile(finite, 95)),
    }


def resolve_bands(scene: RasterSceneData, mapping: dict[str, int]) -> dict[str, int]:
    """Validate a band mapping (e.g. ``{"nir": 8, "red": 4, "blue": 2}``).

    Band indices are 1-based. Raises :class:`BandMappingError` when a mapped
    index is outside the scene's band count.
    """
    band_count = len(scene.bands)
    invalid = {
        name: index
        for name, index in mapping.items()
        if not isinstance(index, int) or not (1 <= index <= band_count)
    }
    if invalid:
        raise BandMappingError(
            f"Band mapping out of range for a {band_count}-band scene: {invalid}. "
            f"Band indices are 1-based."
        )
    return {name: int(index) for name, index in mapping.items()}


def _check_shapes(a: np.ndarray, b: np.ndarray, name: str) -> None:
    if a.shape != b.shape:
        raise ValueError(f"{name} requires equal-shaped inputs, got {a.shape} and {b.shape}")


def validate_index(name: str, mapping: dict[str, int], required: set[str]) -> dict[str, int]:
    """Validate that all required bands are present in a mapping."""
    missing = sorted(required - set(mapping))
    if missing:
        raise BandMappingError(
            f"{name} requires bands {sorted(required)}, but mapping is missing {missing}"
        )
    return {k: mapping[k] for k in required}


def compute_index(
    name: str,
    arrays: dict[str, np.ndarray],
    mapping: dict[str, int],
    required: set[str],
) -> np.ndarray:
    """Dispatch to the index function for the mapped band arrays.

    ``arrays`` maps band names to raw numpy arrays; ``mapping`` maps band
    names to 1-based indices (used only for validation).
    """
    _ = mapping
    validate_index(name, mapping, required)
    if name.upper() == "NDVI":
        return ndvi(arrays["nir"], arrays["red"])
    if name.upper() == "EVI":
        return evi(arrays["nir"], arrays["red"], arrays["blue"])
    raise BandMappingError(f"Unsupported spectral index: {name}")


__all__: list[str] = [
    "band_statistics",
    "compute_index",
    "evi",
    "ndvi",
    "resolve_bands",
    "validate_index",
]
